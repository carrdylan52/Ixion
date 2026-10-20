// Shared protocol tests, vendored into each port's focused GoogleTest target.
#include "ixion_delivery_lock.hpp"
#include "ixion_delivery.hpp"
#include "platform/files.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <random>
#include <stdexcept>

namespace {
using namespace ixion::delivery;
class IxionDelivery : public testing::Test {
protected:
    Path root, ledger, cursor;
    bool owned = false;
    const std::string identity = "0123456789abcdef0123456789abcdef";
    std::string error;
    void SetUp() override {
        const char *base = std::getenv("IXION_LEDGER_TEST_ROOT");
        const Path parent = base ? Path(base) : std::filesystem::temp_directory_path();
        std::random_device random;
        root = parent / ("ledger-test-" + std::to_string(random()) + "-" + std::to_string(random()));
        owned = std::filesystem::create_directory(root);
        ASSERT_TRUE(owned);
        ledger = root / "ledger.jsonl";
        cursor = root / "dc1-saves" / "ixion-delivery.cursor.json";
        std::filesystem::create_directory(cursor.parent_path());
        ASSERT_TRUE(Write(ledger, Initial()));
        ASSERT_TRUE(Write(cursor, CursorText({identity, 0})));
        ASSERT_TRUE(Write(ConsumedPath(ledger), ConsumedText({identity, 0})));
        ASSERT_TRUE(Write(root / kDisposableMarker, Marker(identity)));
    }
    void TearDown() override { if (owned) std::filesystem::remove_all(root); }
    std::string Header() {
        return Json{{"version", kLedgerVersion}, {"ledger", identity}, {"cursor", cursor.string()}}.dump() + "\n";
    }
    std::string Initial() { return NewLedgerText(identity, cursor.string()); }
    static std::string Marker(const std::string &id) {
        return Json{{"version", 2u}, {"ledger_format", 2u}, {"ledger", id}}.dump() + "\n";
    }
    static std::string Seal(const std::string &body, uint64_t count) { return body + Trailer(body, count); }
    static std::string Body(const std::string &text) { return text.substr(0, text.rfind('\n', text.size() - 2) + 1); }
    static bool Write(const Path &path, const std::string &text) {
        return FilesWrite(path, text.data(), text.size(), true) == FilesResult::kWritten;
    }
    bool Add(std::string event = "room:session:1:enemy:0") {
        uint64_t seq = 0;
        bool added = false;
        return Append(ledger, event, 123u, Write, seq, added, error);
    }
    uint64_t CursorSeq() {
        std::string text;
        Cursor value;
        EXPECT_TRUE(Read(cursor, text, error));
        EXPECT_TRUE(ParseCursor(text, value, error));
        return value.seq;
    }
    std::string Text() {
        std::string text;
        EXPECT_TRUE(Read(ledger, text, error));
        return text;
    }
};

TEST_F(IxionDelivery, AppendPreservesPrefixAndDeduplicatesEvent) {
    const std::string prefix = Header();
    ASSERT_TRUE(Add());
    std::string first;
    ASSERT_TRUE(Read(ledger, first, error));
    EXPECT_EQ(first.substr(0, prefix.size()), prefix);
    uint64_t seq = 0;
    bool added = true;
    ASSERT_TRUE(Append(ledger, "room:session:1:enemy:0", 124u, Write, seq, added, error));
    EXPECT_EQ(seq, 1u);
    EXPECT_FALSE(added);
    std::string second;
    ASSERT_TRUE(Read(ledger, second, error));
    EXPECT_EQ(first, second);
    ASSERT_TRUE(Add("room:session:2:enemy:0"));
    ASSERT_TRUE(Read(ledger, second, error));
    // Every earlier header and record byte is kept; only the trailer moves.
    EXPECT_EQ(second.substr(0, Body(first).size()), Body(first));
}

TEST_F(IxionDelivery, HistoryDigestsMatchStandardSha256AndCanonicalRecordBytes) {
    EXPECT_EQ(Sha256(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    EXPECT_EQ(Sha256("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    EXPECT_EQ(Sha256("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
              "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
    EXPECT_EQ(Sha256(std::string(1000000, 'a')),
              "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    ASSERT_TRUE(Add("room:a"));
    Ledger parsed;
    ASSERT_TRUE(ParseLedger(Text(), parsed, error));
    const auto bound = BindConsumed(parsed, 1);
    // Independently computed with Python hashlib over the documented JSON/event lines.
    EXPECT_EQ(bound.prefix_sha256, "99c73b75199c665979d5b3adfc678936e4520694339a909bdccf0915e9ac1907");
    EXPECT_EQ(bound.events_sha256, "aa5c825b226b43fa51701c49b5d6b1b421b4dd452f496300b84491429ec9670f");
}

TEST_F(IxionDelivery, ConsumedPrefixBindsAllFieldsButAllowsCanonicalReformatAndNewTail) {
    ASSERT_TRUE(Add("room:a"));
    int grants = 0;
    uint64_t applied = 0;
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    // Whitespace/key order in an otherwise identical ledger is not history.
    const std::string reformatted = Header() +
        "{ \"seq\":1, \"source_game\":\"dc2\", \"source_event\":\"room:a\", \"item\":145, \"created\":123 }\n";
    ASSERT_TRUE(Write(ledger, Seal(reformatted, 1)));
    ASSERT_TRUE(Add("room:b")) << error; // Tail is outside the consumed prefix.
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 2);
    const std::string current = Text();
    {
        std::string body = Body(current);
        const auto at = body.find("\"created\":123");
        // The first consumed line was reformatted and remains preserved by Append.
        ASSERT_NE(at, std::string::npos);
        body.replace(at, 13, "\"created\":124");
        ASSERT_TRUE(Write(ledger, Seal(body, 2)));
        int writes = 0;
        auto write = [&](const Path &, const std::string &) { ++writes; return true; };
        uint64_t seq = 0;
        bool added = true, retryable = true;
        std::string event;
        EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root / "dc2-saves", 124,
                                     write, seq, added, event, retryable, error));
        EXPECT_FALSE(added);
        EXPECT_FALSE(retryable);
        EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
        EXPECT_NE(error.find("consumed history mismatch"), std::string::npos) << error;
        EXPECT_EQ(grants, 2);
        EXPECT_EQ(writes, 0);
    }
}

TEST_F(IxionDelivery, MissingLegacyOrResealedWrongHistoryBindingRefusesEvenDuplicatePublish) {
    ASSERT_TRUE(Add("kill:" + identity + ":d01inter:0:1:e0:native"));
    int grants = 0;
    uint64_t applied = 0;
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    Ledger parsed;
    ASSERT_TRUE(ParseLedger(Text(), parsed, error));
    const auto valid = BindConsumed(parsed, 1);
    auto wrong_prefix = valid, wrong_events = valid;
    wrong_prefix.prefix_sha256 = Sha256("wrong");
    wrong_events.events_sha256 = Sha256("wrong");
    const std::string legacy = CursorText({identity, 1});
    const std::vector<std::string> bad = {legacy + Trailer(legacy, 1),
        ConsumedText(wrong_prefix), ConsumedText(wrong_events), ""};
    for (const auto &text : bad) {
        if (text.empty()) std::filesystem::remove(ConsumedPath(ledger));
        else ASSERT_TRUE(Write(ConsumedPath(ledger), text));
        int writes = 0;
        auto write = [&](const Path &, const std::string &) { ++writes; return true; };
        uint64_t seq = 0;
        bool added = true, retryable = true;
        std::string event;
        EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root / "dc2-saves", 124,
                                     write, seq, added, event, retryable, error));
        EXPECT_FALSE(added);
        EXPECT_FALSE(retryable);
        EXPECT_FALSE(Add()); // Generic append cannot bypass the same binding.
        EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
        EXPECT_EQ(writes, 0);
        EXPECT_EQ(grants, 1);
    }
}

TEST_F(IxionDelivery, SaveRootEqualToRunIsRefused) {
    EXPECT_FALSE(DisposableRun(ledger, identity, root, error));
}

TEST_F(IxionDelivery, LegacyLedgerRefusesAppendAndConsumeRegardlessOfCursor) {
    const std::string header = Json{{"version", 1u}, {"ledger", identity}, {"cursor", cursor.string()}}.dump() + "\n";
    const std::string record = "{\"seq\":1,\"source_game\":\"dc2\",\"source_event\":\"kill:" + identity +
        ":d01inter:0:1:e0:dc1-e104a\",\"item\":145,\"created\":123}\n";
    const std::string legacy = Seal(header + record, 1);
    ASSERT_TRUE(Write(ledger, legacy));
    int grants = 0, writes = 0;
    auto write = [&](const Path &, const std::string &) { ++writes; return true; };
    uint64_t seq = 0, applied = 99;
    bool added = true;
    EXPECT_FALSE(Append(ledger, "kill:" + identity + ":d01inter:0:1:e0:native", 124u,
                        write, seq, added, error));
    EXPECT_FALSE(added);
    EXPECT_NE(error.find("legacy ledger version 1"), std::string::npos) << error;
    for (uint64_t consumed : {0u, 1u}) {
        ASSERT_TRUE(Write(cursor, CursorText({identity, consumed})));
        EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
        EXPECT_EQ(applied, 0u);
        EXPECT_EQ(CursorSeq(), consumed);
        EXPECT_NE(error.find("legacy ledger version 1"), std::string::npos) << error;
    }
    EXPECT_EQ(writes, 0);
    EXPECT_EQ(grants, 0);
    EXPECT_EQ(Text(), legacy);
}

TEST_F(IxionDelivery, ResealedLegacyAndMixedHistoryWithOriginalMarkerRefuseAllDeliveryPaths) {
    const std::string old_marker = Json{{"version", 1u}, {"ledger", identity}}.dump() + "\n";
    ASSERT_TRUE(Write(root / kDisposableMarker, old_marker));
    const std::string old_record = "{\"seq\":1,\"source_game\":\"dc2\",\"source_event\":\"kill:" + identity +
        ":d01inter:0:1:e0:dc1-e104a\",\"item\":145,\"created\":123}\n";
    const std::string current_record = "{\"seq\":2,\"source_game\":\"dc2\",\"source_event\":\"kill:" + identity +
        ":d01inter:0:1:e0:native\",\"item\":145,\"created\":124}\n";
    for (bool mixed : {false, true}) {
        const std::string text = Seal(Header() + old_record + (mixed ? current_record : ""), mixed ? 2 : 1);
        Ledger parsed;
        ASSERT_TRUE(ParseLedger(text, parsed, error)) << error;
        ASSERT_TRUE(Write(ledger, text));
        ASSERT_TRUE(Write(cursor, CursorText({identity, 1})));
        int writes = 0, grants = 0;
        auto write = [&](const Path &, const std::string &) { ++writes; return true; };
        uint64_t seq = 0, applied = 99;
        bool added = true, retryable = true;
        std::string event;
        EXPECT_FALSE(Append(ledger, "kill:" + identity + ":d01inter:0:1:e1:native", 125u,
                            write, seq, added, error));
        EXPECT_FALSE(added);
        EXPECT_NE(error.find("ledger v2 binding"), std::string::npos) << error;
        EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e1:native", root / "dc2-saves", 125u,
                                     write, seq, added, event, retryable, error));
        EXPECT_FALSE(added);
        EXPECT_FALSE(retryable);
        EXPECT_NE(error.find("ledger v2 binding"), std::string::npos) << error;
        EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
        EXPECT_NE(error.find("ledger v2 binding"), std::string::npos) << error;
        EXPECT_EQ(applied, 0u);
        EXPECT_EQ(writes, 0);
        EXPECT_EQ(grants, 0);
        EXPECT_EQ(CursorSeq(), 1u);
        EXPECT_EQ(Text(), text);
        std::string after;
        ASSERT_TRUE(Read(root / kDisposableMarker, after, error));
        EXPECT_EQ(after, old_marker);
    }
}

TEST_F(IxionDelivery, MarkerRequiresVersionTwoFormatTwoAndThisLedger) {
    ASSERT_TRUE(Add());
    const std::string before = Text();
    const Json valid{{"version", 2u}, {"ledger_format", 2u}, {"ledger", identity}};
    for (const char *field : {"version", "ledger_format", "ledger"}) {
        std::vector<Json> bad;
        Json absent = valid;
        absent.erase(field);
        bad.push_back(absent);
        for (const auto &value : {Json(1u), Json(3u), Json("2"), Json(nullptr), Json(true), Json(2.5)}) {
            Json changed = valid;
            changed[field] = value;
            bad.push_back(changed);
        }
        if (std::string(field) == "ledger") {
            Json foreign = valid;
            foreign[field] = "abcdef0123456789abcdef0123456789";
            bad.push_back(foreign);
        }
        for (const auto &marker : bad) {
            SCOPED_TRACE(marker.dump());
            ASSERT_TRUE(Write(root / kDisposableMarker, marker.dump() + "\n"));
            EXPECT_FALSE(DisposableRun(ledger, identity, root / "dc2-saves", error));
            int writes = 0, grants = 0;
            uint64_t seq = 0, applied = 99;
            bool added = true, retryable = true;
            std::string event;
            auto write = [&](const Path &, const std::string &) { ++writes; return true; };
            EXPECT_FALSE(Append(ledger, "room:new", 125u, write, seq, added, error));
            EXPECT_FALSE(added);
            EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root / "dc2-saves", 125u,
                                         write, seq, added, event, retryable, error));
            EXPECT_FALSE(added);
            EXPECT_FALSE(retryable);
            EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
            EXPECT_EQ(applied, 0u);
            EXPECT_EQ(writes, 0);
            EXPECT_EQ(grants, 0);
            EXPECT_EQ(CursorSeq(), 0u);
            EXPECT_EQ(Text(), before);
        }
    }
    ASSERT_TRUE(Write(root / kDisposableMarker, valid.dump() + "\n"));
    EXPECT_TRUE(DisposableRun(ledger, identity, root / "dc2-saves", error)) << error;
}

TEST_F(IxionDelivery, RejectsUnknownItemSequenceGapDuplicateAndTornTail) {
    ASSERT_TRUE(Add());
    std::string text;
    ASSERT_TRUE(Read(ledger, text, error));
    Json record = Json::parse(text.substr(text.find('\n') + 1, text.find('\n', text.find('\n') + 1) - text.find('\n') - 1));
    Ledger parsed;
    ASSERT_TRUE(ParseLedger(Seal(Header() + record.dump() + "\n", 1), parsed, error)) << error;
    for (const auto &bad : {Json(146u), Json("145"), Json(-1), Json(1.5)}) {
        record["item"] = bad;
        EXPECT_FALSE(ParseLedger(Seal(Header() + record.dump() + "\n", 1), parsed, error));
    }
    record["item"] = 145u;
    record["seq"] = 2u;
    EXPECT_FALSE(ParseLedger(Seal(Header() + record.dump() + "\n", 1), parsed, error));
    record["seq"] = 1u;
    const auto line = record.dump() + "\n";
    record["seq"] = 2u;
    EXPECT_FALSE(ParseLedger(Seal(Header() + line + record.dump() + "\n", 2), parsed, error));
    EXPECT_FALSE(ParseLedger(text.substr(0, text.size() - 1), parsed, error));
}

TEST_F(IxionDelivery, ChecksumMatchesTheLauncherFnv1a64) {
    // tools/ledger.py computes the same values; its initial ledger must parse.
    EXPECT_EQ(Fnv1a64(""), "cbf29ce484222325");
    EXPECT_EQ(Fnv1a64("a"), "af63dc4c8601ec8c");
    const std::string header = "{\"version\":2,\"ledger\":\"" + identity + "\",\"cursor\":\"" + cursor.generic_string() + "\"}\n";
    const std::string python = header + "{\"end\":0,\"fnv1a64\":\"" + Fnv1a64(header) + "\"}\n";
    Ledger parsed;
    EXPECT_TRUE(ParseLedger(python, parsed, error)) << error;
}

TEST_F(IxionDelivery, BoundaryTruncationAndEditsAreRefused) {
    ASSERT_TRUE(Add("room:a"));
    ASSERT_TRUE(Add("room:b"));
    const std::string text = Text();
    Ledger parsed;
    ASSERT_TRUE(ParseLedger(text, parsed, error)) << error;
    ASSERT_EQ(parsed.records.size(), 2u);
    // Cut after the header, after record 1 and after record 2 (trailer lost).
    for (size_t at = text.find('\n'); at + 1 < text.size(); at = text.find('\n', at + 1)) {
        EXPECT_FALSE(ParseLedger(text.substr(0, at + 1), parsed, error)) << "cut at " << at;
        EXPECT_NE(error.find("refusing"), std::string::npos) << error;
    }
    // A cut ledger whose trailer was rebuilt with the old count still fails.
    const std::string one = Body(text).substr(0, Body(text).rfind('\n', Body(text).size() - 2) + 1);
    EXPECT_FALSE(ParseLedger(one + Trailer(Body(text), 2), parsed, error));
    std::string edited = text;
    edited.replace(edited.find("\"created\":123"), 13, "\"created\":124");
    EXPECT_FALSE(ParseLedger(edited, parsed, error));
    EXPECT_NE(error.find("checksum"), std::string::npos) << error;
    // A truncated ledger delivers nothing.
    ASSERT_TRUE(Write(ledger, Body(text)));
    int grants = 0;
    uint64_t applied = 0;
    EXPECT_FALSE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 0);
}

TEST_F(IxionDelivery, CursorDurableBeforeGrantAndRestartDoesNotRegrant) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &r) {
        EXPECT_EQ(CursorSeq(), r.seq);
        std::string text;
        Consumed acked;
        EXPECT_TRUE(Read(ConsumedPath(ledger), text, error));
        EXPECT_TRUE(ParseConsumed(text, acked, error));
        EXPECT_EQ(acked.seq, r.seq);
        ++grants;
    }, applied, error));
    EXPECT_EQ(applied, 1u);
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(applied, 0u);
    EXPECT_EQ(grants, 1);
}

TEST_F(IxionDelivery, ConsumedCursorRewindRefusesPollingAndRelaunch) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    ASSERT_EQ(grants, 1);
    const std::string ledger_before = Text();
    std::string ack_before, marker_before;
    ASSERT_TRUE(Read(ConsumedPath(ledger), ack_before, error));
    ASSERT_TRUE(Read(root / kDisposableMarker, marker_before, error));
    // B5-N1 literally edits only the genuine same-ledger cursor from 1 to 0.
    ASSERT_TRUE(Write(cursor, CursorText({identity, 0})));
    for (int poll = 0; poll < 2; ++poll) {
        // Consume has no process-local dedupe: the second call also models relaunch.
        int writes = 0;
        auto write = [&](const Path &p, const std::string &text) { ++writes; return Write(p, text); };
        std::string last_error; // Fresh process diagnostic state also logs refusal.
        testing::internal::CaptureStderr();
        const bool ok = Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error);
        if (!ok) LogConsumeRefusal(error, last_error); // Same reporter as DC1 safe-point.
        const std::string log = testing::internal::GetCapturedStderr();
        EXPECT_FALSE(ok);
        EXPECT_NE(log.find("ixion ledger refused: consumed high-water disagrees with cursor"), std::string::npos) << log;
        EXPECT_NE(error.find("consumed high-water disagrees with cursor"), std::string::npos) << error;
        EXPECT_EQ(applied, 0u);
        EXPECT_EQ(writes, 0);
        EXPECT_EQ(grants, 1);
        EXPECT_EQ(CursorSeq(), 0u);
        EXPECT_EQ(Text(), ledger_before);
        std::string after;
        ASSERT_TRUE(Read(ConsumedPath(ledger), after, error));
        EXPECT_EQ(after, ack_before);
        ASSERT_TRUE(Read(root / kDisposableMarker, after, error));
        EXPECT_EQ(after, marker_before);
    }
}

TEST_F(IxionDelivery, CrashBetweenProgressWritesLosesButNeverDuplicates) {
    ASSERT_TRUE(Add());
    int grants = 0, writes = 0;
    uint64_t applied = 0;
    auto crash = [&](const Path &p, const std::string &text) {
        if (++writes == 2) throw std::runtime_error("crash between progress writes");
        return Write(p, text);
    };
    EXPECT_THROW(Consume(ledger, cursor, crash, [&](const Record &) { ++grants; }, applied, error), std::runtime_error);
    EXPECT_EQ(grants, 0);
    EXPECT_EQ(CursorSeq(), 0u);
    EXPECT_FALSE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_NE(error.find("consumed high-water disagrees with cursor"), std::string::npos) << error;
    EXPECT_EQ(grants, 0);
}

TEST_F(IxionDelivery, EitherProgressWriteMayFailBeforeOrAfterPublicationWithoutDuplicate) {
    ASSERT_TRUE(Add());
    for (int fail_at : {1, 2}) for (bool publish : {false, true}) for (bool crash : {false, true}) {
        SCOPED_TRACE(std::to_string(fail_at) + " publish=" + std::to_string(publish) + " crash=" + std::to_string(crash));
        ASSERT_TRUE(Write(cursor, CursorText({identity, 0})));
        ASSERT_TRUE(Write(ConsumedPath(ledger), ConsumedText({identity, 0})));
        int grants = 0, writes = 0;
        uint64_t applied = 0;
        auto interrupted = [&](const Path &p, const std::string &text) {
            if (++writes != fail_at) return Write(p, text);
            if (publish) EXPECT_TRUE(Write(p, text));
            if (crash) throw std::runtime_error("simulated progress write crash");
            return false; // May already be published (e.g. directory sync failure).
        };
        if (crash) {
            EXPECT_THROW(Consume(ledger, cursor, interrupted, [&](const Record &) { ++grants; }, applied, error), std::runtime_error);
        } else {
            EXPECT_FALSE(Consume(ledger, cursor, interrupted, [&](const Record &) { ++grants; }, applied, error));
            EXPECT_NE(error.find(fail_at == 1 ? "consumed high-water commit failed" : "cursor commit failed"), std::string::npos) << error;
        }
        EXPECT_EQ(grants, 0);
        const bool disagrees = (fail_at == 1 && publish) || (fail_at == 2 && !publish);
        for (int poll = 0; poll < 2; ++poll) {
            EXPECT_EQ(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error), !disagrees) << error;
            if (disagrees) EXPECT_NE(error.find("disagrees with cursor"), std::string::npos) << error;
        }
        // Only a failure before the first publication can be retried for a grant.
        EXPECT_EQ(grants, fail_at == 1 && !publish ? 1 : 0);
    }
}

TEST_F(IxionDelivery, LoweredSealedHighWaterCannotOverrideTheCommittedCursor) {
    ASSERT_TRUE(Add());
    int grants = 0, writes = 0;
    uint64_t applied = 0;
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    // Reverse single-file attack: even a correctly resealed lower ack refuses.
    ASSERT_TRUE(Write(ConsumedPath(ledger), ConsumedText({identity, 0})));
    auto write = [&](const Path &, const std::string &) { ++writes; return true; };
    EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_NE(error.find("disagrees with cursor"), std::string::npos) << error;
    EXPECT_EQ(grants, 1);
    EXPECT_EQ(writes, 0);
    EXPECT_EQ(CursorSeq(), 1u);
}

TEST_F(IxionDelivery, MissingDamagedForeignOrAheadHighWaterNeverInitializesOrGrants) {
    ASSERT_TRUE(Add());
    const std::string valid = ConsumedText({identity, 0});
    std::string edited = valid;
    edited.replace(edited.find("\"seq\":0"), 7, "\"seq\":1"); // Keep old checksum.
    const std::vector<std::string> bad = {"{}", CursorText({identity, 0}), valid.substr(0, valid.size() - 1),
        edited, valid + valid, ConsumedText({"abcdef0123456789abcdef0123456789", 0}),
        ConsumedText({identity, 2}), CursorText({identity, 0}) + Trailer(CursorText({identity, 0}), 1)};
    int grants = 0, writes = 0;
    uint64_t applied = 0;
    auto write = [&](const Path &, const std::string &) { ++writes; return true; };
    for (const auto &text : bad) {
        SCOPED_TRACE(text);
        ASSERT_TRUE(Write(ConsumedPath(ledger), text));
        EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
        EXPECT_NE(error.find("consumed high-water"), std::string::npos) << error;
        EXPECT_EQ(applied, 0u);
    }
    std::filesystem::remove(ConsumedPath(ledger));
    EXPECT_FALSE(Consume(ledger, cursor, write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_NE(error.find("fresh disposable run"), std::string::npos) << error;
    EXPECT_FALSE(std::filesystem::exists(ConsumedPath(ledger)));
    EXPECT_EQ(grants, 0);
    EXPECT_EQ(writes, 0);
}

TEST_F(IxionDelivery, MultipleDeliveriesCommitBothProgressFilesBeforeEveryGrant) {
    ASSERT_TRUE(Add("room:a"));
    ASSERT_TRUE(Add("room:b"));
    ASSERT_TRUE(Add("room:c"));
    uint64_t applied = 0;
    int grants = 0;
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &r) {
        EXPECT_EQ(CursorSeq(), r.seq);
        std::string text;
        Consumed acked;
        ASSERT_TRUE(Read(ConsumedPath(ledger), text, error));
        ASSERT_TRUE(ParseConsumed(text, acked, error));
        EXPECT_EQ(acked.seq, r.seq);
        Ledger parsed;
        ASSERT_TRUE(ParseLedger(Text(), parsed, error));
        const auto bound = BindConsumed(parsed, r.seq);
        EXPECT_EQ(acked.prefix_sha256, bound.prefix_sha256);
        EXPECT_EQ(acked.events_sha256, bound.events_sha256);
        ++grants;
    }, applied, error));
    EXPECT_EQ(applied, 3u);
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(applied, 0u);
    EXPECT_EQ(grants, 3);
}

TEST_F(IxionDelivery, FailedCursorCommitNeverCallsGrant) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    EXPECT_FALSE(Consume(ledger, cursor, [](const Path &, const std::string &) { return false; },
                         [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 0);
    EXPECT_EQ(CursorSeq(), 0u);
}

TEST_F(IxionDelivery, CrashAfterCursorBeforeGrantLosesButNeverDuplicates) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    EXPECT_THROW(Consume(ledger, cursor, Write, [&](const Record &) {
        throw std::runtime_error("simulated process loss before native grant");
    }, applied, error), std::runtime_error);
    EXPECT_EQ(CursorSeq(), 1u);
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 0);
}

TEST_F(IxionDelivery, CrashAfterGrantNeverDuplicates) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    EXPECT_THROW(Consume(ledger, cursor, Write, [&](const Record &) {
        ++grants;
        throw std::runtime_error("simulated process loss after native grant");
    }, applied, error), std::runtime_error);
    ASSERT_TRUE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 1);
}

TEST_F(IxionDelivery, MissingCorruptOrWrongLedgerCursorRefusesReplay) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    for (const auto &bad : {std::string("{}"), CursorText({identity, 2}),
                           CursorText({"abcdef0123456789abcdef0123456789", 0})}) {
        ASSERT_TRUE(Write(cursor, bad));
        EXPECT_FALSE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    }
    std::filesystem::remove(cursor);
    EXPECT_FALSE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 0);
}

TEST_F(IxionDelivery, DifferentRecipientCannotConsumeTheSameLedger) {
    ASSERT_TRUE(Add());
    Path other = root / "other-cursor.json";
    ASSERT_TRUE(Write(other, CursorText({identity, 0})));
    uint64_t applied = 0;
    int grants = 0;
    EXPECT_FALSE(Consume(ledger, other, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_EQ(grants, 0);
}

TEST_F(IxionDelivery, MissingOrForeignDisposableMarkerRefusesDelivery) {
    ASSERT_TRUE(Add());
    int grants = 0;
    uint64_t applied = 0;
    const Path marker = root / kDisposableMarker;
    ASSERT_TRUE(Write(marker, Marker("abcdef0123456789abcdef0123456789")));
    EXPECT_FALSE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_NE(error.find("marker"), std::string::npos) << error;
    std::filesystem::remove(marker);
    EXPECT_FALSE(Consume(ledger, cursor, Write, [&](const Record &) { ++grants; }, applied, error));
    EXPECT_NE(error.find("marker"), std::string::npos) << error;
    EXPECT_EQ(grants, 0);
    EXPECT_EQ(CursorSeq(), 0u);
    const std::string before = Text();
    uint64_t seq = 0;
    bool added = false, retryable = true;
    std::string event;
    EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root, 123u, Write, seq, added, event,
                                 retryable, error));
    EXPECT_FALSE(retryable);
    EXPECT_EQ(Text(), before);
}

TEST_F(IxionDelivery, WorldKillOutsideTheRunFolderIsRefused) {
    uint64_t seq = 0;
    bool added = false, retryable = true;
    std::string event;
    EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root.parent_path(), 123u, Write, seq, added,
                                 event, retryable, error));
    EXPECT_FALSE(retryable);
    EXPECT_NE(error.find("outside"), std::string::npos) << error;
    EXPECT_EQ(Text(), Initial());
}

TEST_F(IxionDelivery, WorldKillIsLedgerScopedAndARetryAfterAnUnacknowledgedCommitDedupes) {
    uint64_t seq = 0;
    bool added = false, retryable = false;
    std::string event;
    // The write publishes but reports failure (e.g. a directory sync error).
    auto lying = [](const Path &p, const std::string &text) { return Write(p, text) && false; };
    EXPECT_FALSE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root / "saves", 123u, lying, seq, added, event,
                                 retryable, error));
    EXPECT_TRUE(retryable);
    EXPECT_EQ(event, "kill:" + identity + ":d01inter:0:1:e0:native");
    ASSERT_TRUE(AppendWorldKill(ledger, "d01inter:0:1:e0:native", root / "saves", 124u, Write, seq, added, event,
                                retryable, error)) << error;
    EXPECT_FALSE(added);
    EXPECT_EQ(seq, 1u);
    Ledger parsed;
    ASSERT_TRUE(ParseLedger(Text(), parsed, error)) << error;
    EXPECT_EQ(parsed.records.size(), 1u);
}

TEST_F(IxionDelivery, LockExcludesConcurrentOwnersAndReleases) {
    {
        Lock first(ledger);
        ASSERT_TRUE(first.ok());
        Lock second(ledger);
        EXPECT_FALSE(second.ok());
    }
    Lock after(ledger);
    EXPECT_TRUE(after.ok());
}

TEST_F(IxionDelivery, FailedAppendLeavesPublishedLedgerUnchanged) {
    uint64_t seq = 0;
    bool added = false;
    EXPECT_FALSE(Append(ledger, "room:session:1:enemy:0", 123u,
                        [](const Path &, const std::string &) { return false; }, seq, added, error));
    std::string text;
    ASSERT_TRUE(Read(ledger, text, error));
    EXPECT_EQ(text, Initial());
    EXPECT_FALSE(added);
}
} // namespace
