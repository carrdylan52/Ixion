#requires -Version 7.0
param(
 [string]$Mode='Hop',
 [ValidateSet('friendly','faithful')][string]$Balance='friendly',
 [string]$Dc1Data=$env:IXION_DC1_DATA,
 [string]$Dc2Data=$env:IXION_DC2_DATA,
 [string]$RunRoot='',
 [string]$PackageRoot=(Join-Path $PSScriptRoot '../../showcase-local'),
 [switch]$DryRun,
 [int]$SmokeFrames=0,
 [string]$InputPath='',
 [string]$Dc1InputPath='',
 [int]$Dc1Frames=0,
 [string]$AutoSwitch='',
 [ValidateSet('dc1','dc2')][string]$HopStart='dc2'
)
$ErrorActionPreference='Stop'
$PackageRoot=[IO.Path]::GetFullPath($PackageRoot)
if($InputPath){$InputPath=[IO.Path]::GetFullPath($InputPath)}
if($Dc1InputPath){$Dc1InputPath=[IO.Path]::GetFullPath($Dc1InputPath)}
if (!$RunRoot) { $RunRoot=Join-Path $PackageRoot 'runs' }
$RunRoot=[IO.Path]::GetFullPath($RunRoot)
$bin=Join-Path $PackageRoot 'bin'
$d1=if($Dc1Data){[IO.Path]::GetFullPath($Dc1Data)}else{Join-Path $PackageRoot 'data-dc1'}
$d2=if($Dc2Data){[IO.Path]::GetFullPath($Dc2Data)}else{Join-Path $PackageRoot 'data-dc2'}
$names=@(
 'Chest|Cave chest and DC1 atmosphere', 'Inspect|Empty imported cave',
 'Hop|Ledger: kill the rat, F10 to Water in Dark Cloud cave',
 'Opar|Opar fight', 'Ghost|Ghost fight', 'Werewolf|Werewolf (boss tier)',
 'Roster|Fifteen floor-3 monsters', 'Mimic|Mimic and King Mimic', 'KingMimic|Skinned King Mimic',
 'Toan|Toan DC1 combo', 'ToanBurst|Toan charged burst (damage unqualified)',
 'ToanTown|Toan in Palm Brinks', 'Goro|Goro hammer and smash', 'Ungaga|Ungaga combo and charge',
 'Xiao|Xiao slingshot', 'Monica|Monica Opar event 11000', 'MonicaFaithful|Monica faithful goo fight',
 'RandomFloor|DC1 random floor seed 4242', 'Georama|Norune houses and villagers in DC2 editor',
 'Arena|Empty Dran arena', 'Dran|Dran fight (retail balance; long fight)',
 'Ridepod|Ridepod in imported cave', 'RidepodDC1|Ridepod in Dark Cloud cave',
 'ReverseGeorama|DC2 Shed in Norune editor', 'Vanguard|Vanguard in Dark Cloud cave',
 'SecondRoom|Second imported room', 'NativeDC1|Native Dark Cloud in Norune',
 'NativeDC2|Native Dark Chronicle from boot', 'Sfx|Opar with DC1 sound effects'
)
$recipeModes=@('Inspect','Hop','Opar','Ridepod','NativeDC1','NativeDC2')
$picks=@($names | ForEach-Object {$pair=$_.Split('|',2); @{mode=$pair[0];label=$pair[1]}})
if($Mode -eq 'Menu') {
 if($DryRun){@{default='Hop';picks=$picks}|ConvertTo-Json -Depth 5; exit 0}
 Write-Host 'Ixion v3. Every launch creates a fresh disposable session.'
 for($i=0;$i -lt $picks.Count;$i++){Write-Host ("$($i+1). $($picks[$i].label)" + $(if($picks[$i].mode -notin $recipeModes){' [pack recipe not published]'}else{''}))}
 $choice=Read-Host "Pick 1-$($picks.Count), or Q to quit"
 if($choice -eq 'Q'){exit 0}
 $number=0
 if(![int]::TryParse($choice,[ref]$number) -or $number -lt 1 -or $number -gt $picks.Count){throw 'Invalid pick'}
 $Mode=$picks[$number-1].mode
}
if($Mode -notin $picks.mode){throw "Unknown pick: $Mode"}
function QuotedArgs([string[]]$Values){($Values|ForEach-Object {'"'+$_.Replace('"','\"')+'"'}) -join ' '}
function Pack([string]$Name){Join-Path $PackageRoot "packs\$Name"}
function Overlay([string]$Name){Join-Path (Pack $Name) 'data'}
$run=Join-Path $RunRoot ('play-'+$Mode+'-'+[guid]::NewGuid().ToString('N'))
$environment=@{}
$exe=Join-Path $bin 'darkchronicle.exe'
$gameArgs=@('--run-dir',$run,'--data',$d2,'--save',"$run\dc2-saves",'--window','1280x960')
$required=@($exe,$d2)
$c1Mode=$Mode -in @('RidepodDC1','ReverseGeorama','Vanguard','NativeDC1')
$roomMode=$Mode -notin @('NativeDC1','NativeDC2','RidepodDC1','ReverseGeorama','Vanguard','Monica','ToanTown','Georama')
if($roomMode){
 $gameArgs+=@('--jump','dungeon:0:1','--fast-load')
 $environment['DC2_IXION_ROOM']=Join-Path (Pack 'room-d01inter') 'room.json'
 $environment['DC2_IXION_ROOM_FLOOR']='0:1'
 $environment['DC2_IXION_ROOM_MODE']='inspect'
 $environment['DC2_IXION_ROOM_ENCOUNTER']='1'
 $environment['DC2_IXION_ROOM_ATMOS']='0'
 $environment['DC2_IXION_DC1_BALANCE']=$Balance
}
switch($Mode){
 'Chest' {$environment['DC2_IXION_ROOM']=Join-Path (Pack 'props-d01inter-north') 'room.json';$environment['DC2_IXION_ROOM_ATMOS']=Join-Path (Pack 'atmos-r1') 'atmosphere.json';$environment['DC2_IXION_ROOM_ENCOUNTER']='0'}
 'Inspect' {$environment['DC2_IXION_ROOM_ENCOUNTER']='0'}
 {$_ -in @('Opar','Ghost','Werewolf','KingMimic','Sfx')} {
  $id=@{Opar='e104a';Ghost='e42a';Werewolf='e07a';KingMimic='e34a';Sfx='e104a'}[$Mode]
  $pack=@{Opar='opar-r1-overlay';Ghost='ghost-overlay';Werewolf='werewolf-r1-overlay';KingMimic='e34a-dc2';Sfx='opar-r1-overlay'}[$Mode]
  $environment['DC2_IXION_ROOM_DONOR_MONSTER']=$id;$environment['DC2_IXION_EXTRA_DATA']=Overlay $pack
  if($Mode -eq 'Sfx'){$environment['DC2_IXION_EXTRA_DATA']+=';'+(Overlay 'sfx-r1');$environment['DC2_IXION_DC1_SFX']='1'}
 }
 {$_ -in @('Roster','Mimic')} {
  $environment['DC2_IXION_ROOM_DONOR_ROSTER']=if($Mode -eq 'Roster'){'e60a,e03a,e06a,e05a,e103a'}else{'e35a,e34a'}
  $environment['DC2_IXION_ROOM_DONOR_COUNT']=if($Mode -eq 'Roster'){'15'}else{'2'}
  $environment['DC2_IXION_EXTRA_DATA']=Overlay 'roster-r2-all'
 }
 {$_ -in @('Toan','ToanBurst','Goro','Ungaga','Xiao','ToanTown')} {
  $body=@{Toan='toan';ToanBurst='toan';ToanTown='toan';Goro='goro';Ungaga='ungaga';Xiao='xiao'}[$Mode]
  $pack=@{toan='toan-c01d';goro='goro-c06b';ungaga='ungaga-c10b';xiao='xiao-c04b'}[$body]
  $environment['DC2_IXION_PLAYER_BODY']=$body;$environment['DC2_IXION_EXTRA_DATA']=Overlay $pack
  if($Mode -eq 'ToanTown'){$gameArgs+=@('--jump','town:10','--fast-load')}else{$environment['DC2_IXION_PLAYER_COMBAT']='dc1'}
  if($Mode -eq 'ToanBurst'){$environment['DC2_IXION_TOAN_CHARGED_SKILL']='1'}
 }
 {$_ -in @('Monica','MonicaFaithful')} {
  $environment['DC2_IXION_MONICA_FORM']='e104a';$environment['DC2_IXION_EXTRA_DATA']=Overlay 'e104a-monica-s060'
  if($Mode -eq 'Monica'){$gameArgs+=@('--jump','event:11000','--fast-load')}
  else{$environment['DC2_IXION_MONICA_FAITHFUL']='1';$environment['DC2_IXION_EXTRA_DATA']=(Overlay 'monica-cap1')+';'+(Overlay 'e104a-monica-s060')}
 }
 'RandomFloor' {$environment['DC2_IXION_ROOM']=Join-Path (Pack 'randfloor-r2-4242') 'room.json';$environment['DC2_IXION_ROOM_DONOR_ROSTER']='e03a,e06a';$environment['DC2_IXION_ROOM_DONOR_COUNT']='15';$environment['DC2_IXION_EXTRA_DATA']=Overlay 'roster-r2-all';$environment['DC2_IXION_ROOM_ATMOS']=Join-Path (Pack 'randfloor-r2-4242') 'atmosphere.json'}
 'Georama' {$gameArgs=@('--run-dir',$run,'--data',(Overlay 'georama-norune-r4'),'--save',"$run\dc2-saves",'--window','1280x960','--jump','edit:5','--fast-load');$environment['DC2_IXION_GEORAMA_SANDBOX']='1';$required=@($exe,(Overlay 'georama-norune-r4'))}
 {$_ -in @('Arena','Dran')} {$environment['DC2_IXION_ROOM']=Join-Path (Pack 'room-d01boss-arena') 'room.json';if($Mode -eq 'Arena'){$environment['DC2_IXION_ROOM_ENCOUNTER']='0'}else{$environment['DC2_IXION_ROOM_DONOR_MONSTER']='c12a';$environment['DC2_IXION_EXTRA_DATA']=Overlay 'c12a-dc2-r2'}}
 'SecondRoom' {$environment['DC2_IXION_ROOM']=Join-Path (Pack 'room-d01inter2') 'room.json';$environment['DC2_IXION_ROOM_ENCOUNTER']='0'}
 'Ridepod' {$environment['DC2_IXION_ROOM_ENCOUNTER']='0';$gameArgs+=@('--no-debug','--flag','100','--give','135,145,155,165,246')}
}
if($c1Mode){
 $exe=Join-Path $bin 'darkcloud.exe'
 $jump=if($Mode -in @('ReverseGeorama','NativeDC1')){'edit:0'}else{'dungeon:0'}
 $gameArgs=@('--data',$d1,'--save',"$run\dc1-saves",'--jump',$jump,'--fast-load','--width','1280','--height','960')
 $required=@($exe,$d1)
 if($Mode -eq 'RidepodDC1'){$environment['DC_IXION_RIDEPOD']='1';$environment['DC_IXION_RIDEPOD_PACK']=Pack 'ridepod-dc1-r3-final';$environment['DC_AUDIO']='off'}
 if($Mode -eq 'ReverseGeorama'){$environment['DC_IXION_REVGEO']='1';$environment['DC_IXION_REVGEO_PACK']=Pack 'revgeo-r1'}
 if($Mode -eq 'Vanguard'){$environment['DC_IXION_DC2_MONSTER']='e202a';$environment['DC_IXION_DC2_MONSTER_PACK']=Pack 'dc2mon-e202a-r1';$environment['DC_AUDIO']='off'}
}
if($InputPath){$gameArgs+=@('--input',$InputPath);$required+=$InputPath}
if($SmokeFrames -gt 0){$gameArgs+=@('--offscreen','--frames',"$SmokeFrames",'--screenshot',"$run\frame.png")}
$ledger=''
if($Mode -eq 'Hop'){
 $ledger="$run\ledger.jsonl";$environment['IXION_LEDGER']=$ledger
 $c1=@('--data',$d1,'--save',"$run\dc1-saves",'--jump','dungeon:0','--fast-load','--width','1280','--height','960')
 if($Dc1InputPath){$c1+=@('--input',$Dc1InputPath);$required+=$Dc1InputPath}
 if($SmokeFrames -gt 0 -or $AutoSwitch){$c1+='--offscreen'}
 if($Dc1Frames -gt 0){$c1+=@('--frames',"$Dc1Frames",'--screenshot',"$run\dc1-frame.png")}
 $exe=Join-Path $bin 'ixion.exe'
 $gameArgs=@('--dc1',"$bin\ixion_c1.dll",'--dc1-args',(QuotedArgs $c1),'--dc2',"$bin\ixion_c2.dll",'--dc2-args',(QuotedArgs $gameArgs),'--start',$HopStart,'--ledger',$ledger,'--log',"$run\host.log")
 if($AutoSwitch){$gameArgs+=@('--auto-switch',$AutoSwitch)}
 $required+=@($exe,"$bin\ixion_c1.dll","$bin\ixion_c2.dll",$d1,"$PSScriptRoot\..\ledger.py")
}
foreach($key in $environment.Keys){if($key -in @('DC2_IXION_ROOM','DC2_IXION_ROOM_ATMOS','DC_IXION_RIDEPOD_PACK','DC_IXION_REVGEO_PACK','DC_IXION_DC2_MONSTER_PACK') -and $environment[$key] -ne '0'){$required+=$environment[$key]};if($key -eq 'DC2_IXION_EXTRA_DATA'){$required+=$environment[$key].Split(';')}}
$plan=[ordered]@{mode=$Mode;balance=$Balance;run=$run;exe=$exe;args=$gameArgs;env=$environment;required=@($required|Select-Object -Unique);ledger=$ledger;smoke_frames=$SmokeFrames}
if($DryRun){$plan|ConvertTo-Json -Depth 6;exit 0}
foreach($path in $plan.required){if(!(Test-Path -LiteralPath $path)){throw "Required private file/folder missing: $path"}}
New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
New-Item -ItemType Directory -Path $run | Out-Null
# Clear inherited native and donor selections before applying this pick.
Get-ChildItem Env: | Where-Object {$_.Name -like 'DC2_IXION*' -or $_.Name -like 'DC_IXION*' -or $_.Name -like 'IXION_*' -or $_.Name -in @('DC2_JUMP','DC2_GIVE','DC2_FLAG','DC2_NO_DEBUG','DC2_INPUT','DC_JUMP','DC_GIVE','DC_INPUT')} | ForEach-Object {Remove-Item -LiteralPath ('Env:\'+$_.Name)}
foreach($key in $environment.Keys){Set-Item -LiteralPath ('Env:\'+$key) -Value $environment[$key]}
if($ledger){& python -B "$PSScriptRoot\..\ledger.py" --ledger $ledger --dc1-save "$run\dc1-saves";if($LASTEXITCODE){throw 'Could not initialize disposable ledger'}}
New-Item -ItemType Directory -Path "$run\dc1-saves","$run\dc2-saves" -Force | Out-Null
if($Mode -eq 'Georama'){'ixion-georama-sandbox-v1'|Set-Content "$run\dc2-saves\ixion-georama-sandbox.marker"}
$plan|ConvertTo-Json -Depth 6|Set-Content "$run\launch.json"
Write-Host "Ixion v3 $Mode. Disposable session: $run"
Write-Host 'Cross confirms/attacks; Circle locks on. See PLAYTEST.md for pick-specific controls and caveats.'
if($ledger){Write-Host 'Kill the rat in DC2, press F10, confirm Dark Cloud floor/intro prompts, then wait for Regular Water acquired.'}
Push-Location $run
try {& $exe @gameArgs 2>&1|Tee-Object -FilePath "$run\run.log";$code=$LASTEXITCODE} finally {Pop-Location}
@{exit=$code;exe_sha256=(Get-FileHash $exe).Hash;pngs=@(Get-ChildItem $run -Filter '*.png'|ForEach-Object {@{path=$_.Name;sha256=(Get-FileHash $_.FullName).Hash}})}|ConvertTo-Json -Depth 4|Set-Content "$run\result.json"
Write-Host "Session exit=$code; logs: $run"
exit $code
