<?php
// ========================
// manual_sync.php
// ========================

//CONFIGURATION
$csvDirectory = __DIR__ . '/temp_csv_files'; // Update path if needed

//PLACEHOLDER: API endpoint
$apiUrl = 'https://clickhcm.com/api/attendance';

// PLACEHOLDER: Authentication key/token
$authKey = 'abcd';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $date = $_POST['date'] ?? '';
    if (!$date || !preg_match('/^\d{8}$/', $date)) {
        echo " Invalid date format. Use YYYYMMDD.";
        exit;
    }

    $files = glob("$csvDirectory/attendance_{$date}_*.csv");

    if (empty($files)) {
        echo "No files found for the selected date.";
        exit;
    }

    foreach ($files as $file) {
        if (!file_exists($file) || filesize($file) == 0) {
            continue;
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
            unlink($file);
            echo "Uploaded and deleted: $file<br>";
        } else {
            echo "Failed to upload: $file (HTTP $httpCode)<br>";
        }
    }
} else {
    // ========================
    // Show HTML form
    // ========================
    echo '<h2>Manual CSV Sync</h2>';
    echo '<form method="POST">
            <label>Select Date (YYYYMMDD): <input type="text" name="date" required></label>
            <button type="submit">Sync</button>
          </form>';
}
?>

