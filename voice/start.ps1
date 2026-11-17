# Local Windows microphone rehearsal with barge-in. Use fictional caller details.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'recognizer.ps1')
$engine = New-DeskRecognizer
$tts = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$tts.SelectVoice('Microsoft David Desktop')
$engine.SetInputToDefaultAudioDevice()
$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = (Get-Command python -CommandType Application | Select-Object -First 1).Source
$psi.Arguments = '-u -m helpline.bridge'
$psi.WorkingDirectory = Split-Path $PSScriptRoot
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.CreateNoWindow = $true
$worker = [Diagnostics.Process]::Start($psi)
$detected = Register-ObjectEvent $engine SpeechDetected -MessageData $tts -Action {
    if ($event.MessageData.State -eq [System.Speech.Synthesis.SynthesizerState]::Speaking) {
        $event.MessageData.SpeakAsyncCancelAll()
    }
}
try {
    do {
        $line = $worker.StandardOutput.ReadLine()
        if (-not $line) { break }
        $response = $line | ConvertFrom-Json
        Write-Host $response.reply
        if ($response.stage -eq 'closed') { $tts.Speak($response.reply); break }
        $null = $tts.SpeakAsync($response.reply)
        $result = $engine.Recognize([TimeSpan]::FromSeconds(8))
        $tts.SpeakAsyncCancelAll()
        $utterance = if ($result -and $result.Confidence -ge 0.45) { $result.Text } else { '' }
        $worker.StandardInput.WriteLine((ConvertTo-Json -Compress -InputObject $utterance))
        $worker.StandardInput.Flush()
    } while (-not $worker.HasExited)
} finally {
    Unregister-Event -SourceIdentifier $detected.Name
    Remove-Job -Id $detected.Id -Force
    $worker.StandardInput.Close()
    $worker.Dispose()
    $engine.Dispose()
    $tts.Dispose()
}
