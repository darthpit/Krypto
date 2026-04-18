<?php
header('Content-Type: application/json');

$input = file_get_contents('php://input');
$configPath = __DIR__ . '/../config.json';

// Validate JSON
$decoded = json_decode($input, true);
if (json_last_error() !== JSON_ERROR_NONE || !$decoded) {
    echo json_encode(['success' => false, 'error' => 'Invalid JSON format']);
    exit;
}

// Backup old config
if (file_exists($configPath)) {
    copy($configPath, $configPath . '.bak');
}

// Save new config
if (file_put_contents($configPath, json_encode($decoded, JSON_PRETTY_PRINT))) {
    echo json_encode(['success' => true]);
} else {
    echo json_encode(['success' => false, 'error' => 'Failed to write to config.json']);
}
