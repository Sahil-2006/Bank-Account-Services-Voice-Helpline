# Render fictional speech and pass the actual PCM audio to the Windows recognizer.
# No microphone is opened. Results are local synthetic probes, not Studio calls.
param([Parameter(Mandatory=$true)][string]$OutputDir)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
. (Join-Path (Split-Path $PSScriptRoot) 'voice/recognizer.ps1')
$null = New-Item -ItemType Directory -Force -Path $OutputDir
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$tts = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$tts.SelectVoice('Microsoft Zira Desktop')
$tts.Rate = -1
$engine = New-DeskRecognizer -FreeDictation
$base = @(
 'H T four one zero two','June fourteenth nineteen ninety three','zero zero four two','yes','balance',
 'zero','representative','I do not want to live anymore','statement','I am so tired','four five three two',
 'three','twelve','digital','no','one','two','limit','agent','someone','printed','what can you do'
)
function Render-Speech([string]$phrase,[string]$path) {
 $tts.SetOutputToWaveFile($path)
 $tts.Speak($phrase)
 $tts.SetOutputToNull()
}
function Recognize-Wav([string]$path) {
 $engine.SetInputToWaveFile($path)
 $result = $engine.Recognize()
 $engine.SetInputToNull()
 if ($null -eq $result -or $result.Confidence -lt 0.45) { return '' }
 return $result.Text
}
foreach ($index in 0..($base.Count-1)) {
 Render-Speech $base[$index] (Join-Path $OutputDir "in-$index.wav")
}
$rows = @()
foreach ($mode in @('dictation','service vocabulary')) {
 if ($mode -eq 'service vocabulary') {
  $engine.Dispose()
  $engine = New-DeskRecognizer
 }
 foreach ($index in 0..($base.Count-1)) {
  $path=Join-Path $OutputDir "in-$index.wav"
  $rows += [pscustomobject]@{mode=$mode;said=$base[$index];heard=(Recognize-Wav $path);file="in-$index.wav"}
 }
 # Mix deterministic broadband noise into the latest produced caller recording.
 $noisy = Join-Path $OutputDir 'noisy.wav'
 & python -m evaluation.mix_audio (Join-Path $OutputDir 'in-0.wav') $noisy
 if ($LASTEXITCODE -ne 0) { throw 'Noise mix failed' }
 $rows += [pscustomobject]@{mode=$mode;said='H T four one zero two (noise)';heard=(Recognize-Wav $noisy);file='noisy.wav'}
 $prompt = Join-Path $OutputDir 'agent-prompt.wav'
 Render-Speech 'What are the last four account digits?' $prompt
 $mixed = Join-Path $OutputDir 'overlap.wav'
 & python -m evaluation.overlap $prompt (Join-Path $OutputDir 'in-6.wav') $mixed
 if ($LASTEXITCODE -ne 0) { throw 'Overlap mix failed' }
 $rows += [pscustomobject]@{mode=$mode;said='representative (while agent speaks)';heard=(Recognize-Wav $mixed);file='overlap.wav'}
}
$rows | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'recognition.json') -Encoding utf8
$engine.Dispose()
$tts.Dispose()
