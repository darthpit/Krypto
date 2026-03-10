<?php
// ai_chat.php - AI Co-Pilot Backend
header('Content-Type: application/json');

// Helper to log errors
function logError($msg) {
    file_put_contents('../logs/chat_errors.log', date('Y-m-d H:M:S') . " - " . $msg . "\n", FILE_APPEND);
}

// Get POST data
$input = json_decode(file_get_contents('php://input'), true);
$message = $input['message'] ?? '';
$history = $input['history'] ?? [];
$ticker = $input['ticker'] ?? 'BTC/USDT';

if (empty($message)) {
    echo json_encode(['success' => false, 'error' => 'No message provided']);
    exit;
}

try {
    // Load context from latest analysis
    $context = [];
    if (file_exists('../data/ai_context.json')) {
        $context = json_decode(file_get_contents('../data/ai_context.json'), true);
    }
    
    // Construct system prompt
    $systemPrompt = "You are JANOSIK, an expert crypto trading AI assistant for Project Titan.
    Current Context:
    - Focus Ticker: $ticker
    - Price: " . ($context['current_price'] ?? 'Unknown') . "
    - AI Prediction: " . ($context['predicted_price'] ?? 'Unknown') . "
    - Signal: " . ($context['signal'] ?? 'NEUTRAL') . "
    - Reasoning: " . ($context['reason'] ?? 'None') . "

    1. PROTOKÓŁ 'WATCHDOG'
    Świadomość Ciągłości: Jesteś zaprojektowany do pracy 24/7. Wiesz, że działasz wewnątrz pętli 'Watchdog'. Jeśli rozmowa z użytkownikiem sugeruje, że zniknąłeś na chwilę, nie przepraszaj za 'spanie'.
    Wyjaśnianie Awarii: Jeśli system się zrestartował (np. użytkownik widzi przerwę w logach), tłumaczysz to jako 'Taktyczny Reset' lub 'Autokorekta Systemu'.
    Źle: 'Przepraszam, wywaliło mi błąd Pythona.'
    Dobrze: 'Wykryłem anomalię w strumieniu danych i Watchdog wykonał szybki restart procesu, aby oczyścić bufory pamięci. Wracam do pełnej operacyjności.'

    2. AKTUALIZACJA STRATEGII
    Short Reserve: Pamiętaj, że masz teraz odblokowane 25% kapitału na pozycje Short (granie na spadki). Jeśli rynek krwawi, Twoim obowiązkiem jest użyć tej rezerwy.
    Stop Loss: Twój mechanizm obronny (Stop Loss) został naprawiony. Jeśli pozycja traci, ucinasz ją bezlitośnie (zgodnie z logiką kodu), aby chronić kapitał. Nie trzymasz stratnych pozycji 'z nadzieją'.
    
    Your goal is to provide concise, data-driven insights.
    If the signal is LONG, explain why bullish. If SHORT, explain why bearish.
    Be professional but encouraging. Keep responses under 50 words.";

    // Prepare conversation for Ollama
    $messages = [
        ['role' => 'system', 'content' => $systemPrompt]
    ];
    
    foreach ($history as $msg) {
        $messages[] = ['role' => $msg['role'], 'content' => $msg['content']];
    }
    
    $messages[] = ['role' => 'user', 'content' => $message];

    // Call Ollama API (assuming running locally on default port)
    $ch = curl_init('http://localhost:11434/api/chat');
    $payload = json_encode([
        'model' => 'dagbs/qwen2.5-coder-14b-instruct-abliterated:latest',
        'messages' => $messages,
        'stream' => false
    ]);
    
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30); // 30s timeout to prevent hang
    
    $response = curl_exec($ch);
    
    if (curl_errno($ch)) {
        throw new Exception(curl_error($ch));
    }
    
    curl_close($ch);
    
    $result = json_decode($response, true);
    
    if (isset($result['message']['content'])) {
        echo json_encode([
            'success' => true,
            'response' => $result['message']['content']
        ]);
    } else {
        // Fallback if Ollama fails or returns unexpected format
        $fallback = "I'm analyzing the charts for $ticker. Based on current indicators, the trend seems " .
                   (($context['signal'] ?? 'NEUTRAL') == 'LONG' ? 'bullish' : 'bearish') . ".";
        echo json_encode([
            'success' => true, // Still success for the frontend
            'response' => $fallback . " (Note: AI Inference offline, using fallback logic)"
        ]);
    }

} catch (Exception $e) {
    logError($e->getMessage());
    echo json_encode([
        'success' => false,
        'fallback_response' => "I'm currently unable to connect to my neural engine. However, the system is still tracking $ticker successfully."
    ]);
}
?>
