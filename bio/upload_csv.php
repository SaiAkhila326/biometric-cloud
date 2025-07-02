<?php
// ========================
// upload_csv.php
// ========================

// CONFIGURATION
$csvDirectory = __DIR__ . '/temp_csv_files'; // Update path if needed

// PLACEHOLDER: API endpoint to upload logs
$apiUrl = 'https://clickhcm.com/api/attendance';

// PLACEHOLDER: Authentication key/token
$authKey = 'abcd';

// ========================
// Upload all CSVs
// ========================
$files = glob("$csvDirectory/attendance_*.csv");

foreach ($files as $file) {
    if (!file_exists($file) || filesize($file) == 0) {
        continue; // Skip empty files
    }

    $post = [
        'file' => new CURLFile($file)
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $apiUrl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $post);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "X-Auth-Key: $authKey"
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($httpCode == 200) {
        unlink($file); // ✅ Delete on success
        echo "Uploaded and deleted: $file\n";
    } else {
        echo "Failed to upload: $file (HTTP $httpCode)\n";
    }
}
?>

