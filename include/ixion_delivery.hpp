// Ixion delivery ledger v2. Vendored byte-for-byte by the two ports.
// The launcher owns the ledger; games only append deliveries or consume them.
#pragma once

#include <array>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <limits>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include <nlohmann/json.hpp>

namespace ixion::delivery {
using Json = nlohmann::json;
using Path = std::filesystem::path;
constexpr int kRegularWater = 145;
// v1 includes ambiguous pre-R4 fallback attribution. Never continue it.
// Cursor stays v1. Eligibility for this ledger format requires a v2 run marker.
constexpr unsigned kLedgerVersion = 2;
constexpr unsigned kDisposableMarkerVersion = 2;
constexpr size_t kMaxBytes = 4 * 1024 * 1024;
// Written by the launcher's ledger.py beside the ledger in a fresh run folder.
constexpr const char *kDisposableMarker = "ixion-disposable-run.json";

struct Record {
    uint64_t seq = 0;
    std::string source_event;
    int item = kRegularWater;
    uint64_t created = 0;
};
struct Ledger {
    std::string id;
    std::string cursor_path;
    std::vector<Record> records;
    size_t body_size = 0; // header plus records; the trailer line follows
};
struct Cursor {
    std::string ledger;
    uint64_t seq = 0;
};

// Independent history commitments use SHA-256: resealing the ledger's public
// FNV checksum must not permit a chosen collision against retained history.
inline std::string Sha256(std::string_view bytes) {
    constexpr uint32_t k[] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    std::array<uint32_t, 8> h = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                                0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    auto rotr = [](uint32_t x, unsigned n) { return (x >> n) | (x << (32 - n)); };
    std::string padded(bytes);
    padded += static_cast<char>(0x80);
    while (padded.size() % 64 != 56) padded += '\0';
    const uint64_t bits = static_cast<uint64_t>(bytes.size()) * 8;
    for (int i = 7; i >= 0; --i) padded += static_cast<char>(bits >> (i * 8));
    for (size_t offset = 0; offset < padded.size(); offset += 64) {
        uint32_t w[64]{};
        for (unsigned i = 0; i < 16; ++i)
            for (unsigned j = 0; j < 4; ++j)
                w[i] = (w[i] << 8) | static_cast<unsigned char>(padded[offset + 4 * i + j]);
        for (unsigned i = 16; i < 64; ++i) {
            const uint32_t s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >> 3);
            const uint32_t s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >> 10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        auto v = h;
        for (unsigned i = 0; i < 64; ++i) {
            const uint32_t t1 = v[7] + (rotr(v[4],6) ^ rotr(v[4],11) ^ rotr(v[4],25)) +
                                ((v[4] & v[5]) ^ (~v[4] & v[6])) + k[i] + w[i];
            const uint32_t t2 = (rotr(v[0],2) ^ rotr(v[0],13) ^ rotr(v[0],22)) +
                                ((v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]));
            v = {t1 + t2, v[0], v[1], v[2], v[3] + t1, v[4], v[5], v[6]};
        }
        for (unsigned i = 0; i < 8; ++i) h[i] += v[i];
    }
    std::string result;
    for (uint32_t word : h) {
        char hex[9];
        std::snprintf(hex, sizeof hex, "%08x", static_cast<unsigned>(word));
        result += hex;
    }
    return result;
}
struct Consumed {
    std::string ledger;
    uint64_t seq = 0;
    std::string prefix_sha256 = Sha256("");
    std::string events_sha256 = Sha256("");
};

inline std::string RecordText(const Record &r) {
    return Json{{"seq", r.seq}, {"source_game", "dc2"}, {"source_event", r.source_event},
                {"item", static_cast<unsigned>(r.item)}, {"created", r.created}}.dump() + "\n";
}
// Canonical JSON lines in sequence order; event set in ASCII lexical order,
// one event per line (Event excludes newlines). No header or mutable tail.
inline Consumed BindConsumed(const Ledger &ledger, uint64_t seq) {
    std::string prefix, events;
    std::set<std::string> identities;
    for (const auto &r : ledger.records) {
        if (r.seq > seq) break;
        prefix += RecordText(r);
        identities.insert(r.source_event);
    }
    for (const auto &event : identities) events += event + "\n";
    return {ledger.id, seq, Sha256(prefix), Sha256(events)};
}

inline bool Fail(std::string &error, const char *why) { error = why; return false; }
// Shared with the native DC1 poller so refusal diagnostics can be exercised
// without loading a campaign or invoking its town loop.
inline void LogConsumeRefusal(const std::string &error, std::string &last_error) {
    if (last_error != error) std::fprintf(stderr, "ixion ledger refused: %s\n", error.c_str());
    last_error = error;
}
inline bool Id(const std::string &id) {
    return id.size() == 32 && id.find_first_not_of("0123456789abcdef") == std::string::npos;
}
inline bool Event(const std::string &event) {
    return !event.empty() && event.size() <= 160 &&
           event.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/._-") == std::string::npos;
}
inline bool Unsigned(const Json &j, const char *key) {
    return j.contains(key) && j[key].is_number_unsigned();
}
// The last line of every ledger seals the bytes before it: a cut at any line
// boundary removes it, and an edit changes the checksum.
inline std::string Fnv1a64(std::string_view bytes) {
    uint64_t hash = 14695981039346656037ull;
    for (unsigned char c : bytes) { hash ^= c; hash *= 1099511628211ull; }
    char text[17];
    std::snprintf(text, sizeof text, "%016llx", static_cast<unsigned long long>(hash));
    return text;
}
inline std::string Trailer(std::string_view body, uint64_t count) {
    return Json{{"end", count}, {"fnv1a64", Fnv1a64(body)}}.dump() + "\n";
}
inline std::string NewLedgerText(const std::string &id, const std::string &cursor_path) {
    const std::string header = Json{{"version", kLedgerVersion}, {"ledger", id}, {"cursor", cursor_path}}.dump() + "\n";
    return header + Trailer(header, 0);
}
inline bool ParseLedger(const std::string &text, Ledger &out, std::string &error) {
    out = {};
    if (text.empty() || text.size() > kMaxBytes || text.back() != '\n') return Fail(error, "incomplete or oversized ledger");
    const size_t last = text.rfind('\n', text.size() - 2);
    if (last == std::string::npos) return Fail(error, "ledger trailer missing: truncated; refusing");
    const size_t body_size = last + 1;
    Json trailer = Json::parse(text.substr(body_size, text.size() - 1 - body_size), nullptr, false);
    if (!trailer.is_object() || trailer.size() != 2 || !Unsigned(trailer, "end") ||
        !trailer.contains("fnv1a64") || !trailer["fnv1a64"].is_string())
        return Fail(error, "ledger trailer missing: truncated; refusing");
    if (trailer["fnv1a64"].get<std::string>() != Fnv1a64(std::string_view(text).substr(0, body_size)))
        return Fail(error, "ledger checksum mismatch: truncated or edited; refusing");
    size_t offset = 0;
    std::set<std::string> events;
    while (offset < body_size) {
        size_t end = text.find('\n', offset);
        Json j = Json::parse(text.substr(offset, end - offset), nullptr, false);
        if (!j.is_object()) return Fail(error, "invalid ledger JSON");
        if (offset == 0) {
            if (j.size() != 3 || !Unsigned(j, "version") ||
                !j.contains("ledger") || !j["ledger"].is_string() ||
                !j.contains("cursor") || !j["cursor"].is_string()) return Fail(error, "invalid ledger header");
            if (j["version"] == 1)
                return Fail(error, "legacy ledger version 1 has ambiguous kill attribution; refusing append/consume; initialize a fresh disposable run (no migration)");
            if (j["version"] != kLedgerVersion)
                return Fail(error, "unsupported ledger version; refusing append/consume; initialize a fresh disposable run");
            out.id = j["ledger"].get<std::string>();
            out.cursor_path = j["cursor"].get<std::string>();
            if (!Id(out.id)) return Fail(error, "invalid ledger identity");
            if (out.cursor_path.empty() || !Path(out.cursor_path).is_absolute()) return Fail(error, "invalid recipient cursor");
        } else {
            if (j.size() != 5 || !Unsigned(j, "seq") || !Unsigned(j, "created") ||
                !Unsigned(j, "item") || j["item"] != kRegularWater ||
                !j.contains("source_game") || j["source_game"] != "dc2" ||
                !j.contains("source_event") || !j["source_event"].is_string()) return Fail(error, "invalid delivery or unknown item");
            Record r{j["seq"].get<uint64_t>(), j["source_event"].get<std::string>(), kRegularWater, j["created"].get<uint64_t>()};
            if (r.seq != out.records.size() + 1 || r.created == 0 || !Event(r.source_event) ||
                !events.insert(r.source_event).second) return Fail(error, "non-contiguous sequence or repeated event");
            out.records.push_back(std::move(r));
        }
        offset = end + 1;
    }
    if (out.id.empty()) return Fail(error, "invalid ledger header");
    if (trailer["end"].get<uint64_t>() != out.records.size())
        return Fail(error, "ledger record count mismatch: truncated; refusing");
    out.body_size = body_size;
    return true;
}
inline bool ParseCursor(const std::string &text, Cursor &out, std::string &error) {
    Json j = Json::parse(text, nullptr, false);
    if (!j.is_object() || j.size() != 3 || !Unsigned(j, "version") || j["version"] != 1 ||
        !Unsigned(j, "seq") || !j.contains("ledger") || !j["ledger"].is_string()) return Fail(error, "invalid cursor; refusing replay");
    out = {j["ledger"].get<std::string>(), j["seq"].get<uint64_t>()};
    return Id(out.ledger) || Fail(error, "invalid cursor identity");
}
inline std::string CursorText(const Cursor &cursor) {
    return Json{{"version", 1u}, {"ledger", cursor.ledger}, {"seq", cursor.seq}}.dump() + "\n";
}
// Independent progress evidence lives beside the ledger, not in the save root.
// Never recreate it during consumption: deletion must not reset the lower bound.
inline Path ConsumedPath(const Path &ledger_path) {
    Path result = ledger_path;
    result += ".consumed.jsonl";
    return result;
}
inline std::string ConsumedText(const Consumed &acked) {
    const std::string body = Json{{"version", 2u}, {"ledger", acked.ledger}, {"seq", acked.seq},
        {"prefix_sha256", acked.prefix_sha256}, {"events_sha256", acked.events_sha256}}.dump() + "\n";
    return body + Trailer(body, acked.seq);
}
inline bool ParseConsumed(const std::string &text, Consumed &out, std::string &error) {
    out = {};
    const size_t end = text.find('\n');
    if (text.empty() || text.size() > kMaxBytes || text.back() != '\n' || end == std::string::npos)
        return Fail(error, "incomplete consumed high-water; refusing replay");
    const std::string body = text.substr(0, end + 1);
    Json j = Json::parse(body, nullptr, false);
    Json seal = Json::parse(text.substr(end + 1), nullptr, false);
    auto digest = [&](const char *key) {
        if (!j.contains(key) || !j[key].is_string()) return false;
        const auto value = j[key].get<std::string>();
        return value.size() == 64 && value.find_first_not_of("0123456789abcdef") == std::string::npos;
    };
    if (!j.is_object() || j.size() != 5 || !Unsigned(j, "version") || j["version"] != 2 ||
        !Unsigned(j, "seq") || !j.contains("ledger") || !j["ledger"].is_string() ||
        !Id(j["ledger"].get<std::string>()) || !digest("prefix_sha256") || !digest("events_sha256"))
        return Fail(error, "invalid consumed high-water history binding; initialize a fresh disposable run (no migration)");
    if (!seal.is_object() || seal.size() != 2 ||
        !Unsigned(seal, "end") || seal["end"] != j["seq"] ||
        !seal.contains("fnv1a64") || seal["fnv1a64"] != Fnv1a64(body))
        return Fail(error, "invalid consumed high-water seal; refusing replay");
    out = {j["ledger"].get<std::string>(), j["seq"].get<uint64_t>(),
           j["prefix_sha256"].get<std::string>(), j["events_sha256"].get<std::string>()};
    return true;
}
inline bool Read(const Path &path, std::string &out, std::string &error) {
    std::error_code ec;
    if (!std::filesystem::is_regular_file(path, ec)) return Fail(error, "missing or non-regular delivery file");
    auto size = std::filesystem::file_size(path, ec);
    if (ec || size > kMaxBytes) return Fail(error, "cannot size delivery file");
    std::ifstream file(path, std::ios::binary);
    out.resize(static_cast<size_t>(size));
    if (!file || !file.read(out.data(), out.size())) return Fail(error, "cannot read delivery file");
    return true;
}
// Caller holds the ledger lock, in both publisher and recipient paths.
inline bool VerifyConsumed(const Path &path, const Ledger &ledger, Consumed &acked, std::string &error) {
    std::string text;
    if (!Read(ConsumedPath(path), text, error))
        return Fail(error, "missing or unreadable consumed high-water; refusing replay; initialize a fresh disposable run (no migration)");
    if (!ParseConsumed(text, acked, error)) return false;
    if (acked.ledger != ledger.id || acked.seq > ledger.records.size())
        return Fail(error, "consumed high-water identity changed or ledger rolled back; refusing replay");
    const auto expected = BindConsumed(ledger, acked.seq);
    if (acked.prefix_sha256 != expected.prefix_sha256 || acked.events_sha256 != expected.events_sha256)
        return Fail(error, "consumed history mismatch; refusing append/consume (edited ledger or high-water)");
    return true;
}
inline bool Within(const Path &child, const Path &folder) {
    std::error_code ec;
    Path path = std::filesystem::weakly_canonical(std::filesystem::absolute(child, ec), ec);
    if (ec) return false;
    // Strict containment, matching the launcher: save == run is not a save subfolder.
    path = path.parent_path();
    for (;;) {
        std::error_code same;
        if (std::filesystem::equivalent(path, folder, same) && !same) return true;
        if (!path.has_relative_path()) return false;
        path = path.parent_path();
    }
}
// Delivery is enabled only in a launcher-made run folder: the marker names
// this ledger AND its format, and the participant's own save root lies inside
// that folder. A resealed header cannot upgrade legacy run authorization.
inline bool DisposableRun(const Path &ledger_path, const std::string &ledger_id, const Path &save_root,
                          std::string &error) {
    std::error_code ec;
    const Path run = std::filesystem::absolute(ledger_path, ec).parent_path();
    std::string text;
    if (ec || !Read(run / kDisposableMarker, text, error))
        return Fail(error, "run folder lacks the launcher's disposable-run marker; delivery disabled");
    Json j = Json::parse(text, nullptr, false);
    if (j.is_object() && Unsigned(j, "version") && j["version"] == 1)
        return Fail(error, "legacy disposable-run marker version 1 lacks ledger v2 binding; refusing append/consume; initialize a fresh disposable run (no migration)");
    if (!j.is_object() || j.size() != 3 || !Unsigned(j, "version") || j["version"] != kDisposableMarkerVersion ||
        !Unsigned(j, "ledger_format") || j["ledger_format"] != kLedgerVersion ||
        !j.contains("ledger") || j["ledger"] != ledger_id)
        return Fail(error, "disposable-run marker lacks ledger v2 binding to this ledger; delivery disabled");
    if (!Within(save_root, run)) return Fail(error, "save root is outside the disposable run folder; delivery disabled");
    return true;
}

template<class Write>
bool AppendParsed(const Path &path, const std::string &text, const Ledger &ledger, const std::string &event,
                  uint64_t created, Write write, uint64_t &seq, bool &added, std::string &error) {
    added = false;
    if (!Event(event) || !created) return Fail(error, "invalid source event");
    for (const auto &r : ledger.records) {
        if (r.source_event == event) { seq = r.seq; return true; }
    }
    seq = ledger.records.size() + 1;
    const std::string body = text.substr(0, ledger.body_size) +
        Json{{"seq", seq}, {"source_game", "dc2"}, {"source_event", event},
             {"item", static_cast<unsigned>(kRegularWater)}, {"created", created}}.dump() + "\n";
    const std::string next = body + Trailer(body, seq);
    if (next.size() > kMaxBytes) return Fail(error, "ledger full");
    if (!write(path, next)) return Fail(error, "ledger commit failed");
    added = true;
    return true;
}

// Caller holds the ledger lock. The snapshot is replaced atomically but old
// records are preserved byte-for-byte: logically append-only, no torn tail.
template<class Write>
bool Append(const Path &path, const std::string &event, uint64_t created,
            Write write, uint64_t &seq, bool &added, std::string &error) {
    added = false;
    std::string text;
    Ledger ledger;
    Consumed acked;
    if (!Read(path, text, error) || !ParseLedger(text, ledger, error) ||
        !DisposableRun(path, ledger.id, Path(ledger.cursor_path).parent_path(), error) ||
        !VerifyConsumed(path, ledger, acked, error)) return false;
    return AppendParsed(path, text, ledger, event, created, write, seq, added, error);
}

// One world kill per ledger: the event is "kill:<ledger id>:<stable place>",
// with no process nonce or room generation, so a relaunch, a save reload or a
// respawn re-kill dedupes to added=0. Caller holds the ledger lock. Only an
// unreadable file or failed commit is worth retrying; the rest are refusals.
template<class Write>
bool AppendWorldKill(const Path &path, const std::string &place, const Path &save_root, uint64_t created,
                     Write write, uint64_t &seq, bool &added, std::string &event, bool &retryable,
                     std::string &error) {
    added = false;
    retryable = false;
    std::string text;
    Ledger ledger;
    if (!Read(path, text, error)) { retryable = true; return false; }
    if (!ParseLedger(text, ledger, error) || !DisposableRun(path, ledger.id, save_root, error)) return false;
    Consumed acked;
    if (!VerifyConsumed(path, ledger, acked, error)) return false;
    event = "kill:" + ledger.id + ":" + place;
    if (!AppendParsed(path, text, ledger, event, created, write, seq, added, error)) {
        retryable = error == "ledger commit failed";
        return false;
    }
    return true;
}

// Caller holds ledger then cursor locks through both progress writes and grant.
// The ledger lock also owns ConsumedPath. Only the launcher initializes progress.
// High-water BEFORE cursor BEFORE grant: interruption may lose, never duplicate.
template<class Write, class Grant>
bool Consume(const Path &path, const Path &cursor_path, Write write, Grant grant,
             uint64_t &applied, std::string &error) {
    applied = 0;
    std::string text, cursor_text;
    Ledger ledger;
    Cursor cursor;
    if (!Read(path, text, error) || !ParseLedger(text, ledger, error) ||
        !Read(cursor_path, cursor_text, error) || !ParseCursor(cursor_text, cursor, error)) return false;
    if (cursor.ledger != ledger.id || cursor.seq > ledger.records.size()) return Fail(error, "ledger changed or rolled back; refusing replay");
    std::error_code ec;
    if (!std::filesystem::equivalent(cursor_path, Path(ledger.cursor_path), ec) || ec)
        return Fail(error, "different recipient save root; refusing replay");
    if (!DisposableRun(path, ledger.id, cursor_path.parent_path(), error)) return false;
    Consumed acked;
    const Path consumed_path = ConsumedPath(path);
    if (!VerifyConsumed(path, ledger, acked, error)) return false;
    // Either direction could be a single-file rollback or an interrupted write.
    // Do not repair/reset either file automatically, even if it loses delivery.
    if (acked.seq != cursor.seq)
        return Fail(error, "consumed high-water disagrees with cursor; refusing replay (rollback or interrupted commit)");
    for (const auto &r : ledger.records) {
        if (r.seq <= cursor.seq || r.seq <= acked.seq) continue;
        const auto next = BindConsumed(ledger, r.seq);
        if (!write(consumed_path, ConsumedText(next))) return Fail(error, "consumed high-water commit failed; no grant");
        acked = next;
        if (!write(cursor_path, CursorText({ledger.id, r.seq}))) return Fail(error, "cursor commit failed; no grant");
        cursor.seq = r.seq;
        grant(r); // This may fail or the process may die; that sequence stays consumed.
        ++applied;
    }
    return true;
}
} // namespace ixion::delivery
