function New-DeskRecognizer {
    param([switch]$FreeDictation)
    Add-Type -AssemblyName System.Speech
    $engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new([CultureInfo]'en-US')
    $dictation = [System.Speech.Recognition.DictationGrammar]::new()
    if ($FreeDictation) {
        $engine.LoadGrammar($dictation)
        return $engine
    }
    $commands = @('yes','no','correct','balance','statement','limit','digital','printed','agent','representative',
        'someone','zero','one','two','three','I do not want to live anymore','what can you do','Instant Pay',
        'BankWire','PassBook Express','KitePay','limit only','I am so tired')
    $choices = [System.Speech.Recognition.Choices]::new([string[]]$commands)
    $engine.LoadGrammar([System.Speech.Recognition.Grammar]::new([System.Speech.Recognition.GrammarBuilder]::new($choices)))
    $digits = [System.Speech.Recognition.Choices]::new([string[]]@('one','two','three','four','five','six','seven','eight','nine','zero','oh'))
    foreach ($prefix in @('','H T')) {
        $gb = [System.Speech.Recognition.GrammarBuilder]::new()
        if ($prefix) { $gb.Append($prefix) }
        $gb.Append([System.Speech.Recognition.GrammarBuilder]::new($digits),4,4)
        $engine.LoadGrammar([System.Speech.Recognition.Grammar]::new($gb))
    }
    $dictation.Weight = 0.5
    $engine.LoadGrammar($dictation)
    return $engine
}
