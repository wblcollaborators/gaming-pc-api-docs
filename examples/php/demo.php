<?php

declare(strict_types=1);

/**
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Weblytic Labs
 * See ../../LICENSE-EXAMPLES-MIT.md
 *
 * Walk the booking API locally without a controller or a Windows PC.
 *
 * Usage: php demo.php
 *
 * This process does not mint tokens, does not call heartbeat, and never sets
 * start_confirmed or lock_confirmed to true.
 */

require_once __DIR__ . '/GamingControllerClient.php';
require_once __DIR__ . '/DemoTransport.php';

$transport = new DemoTransport();
$client = new GamingControllerClient(
    'https://controller.example',
    'demo-access-token-not-a-credential',
    30,
    $transport
);

$health = $client->health();
$devices = $client->listDevices(50);
$created = $client->createSession(
    DemoTransport::DEVICE_ID,
    DemoTransport::EXPIRES_AT,
    GamingControllerClient::newIdempotencyKey('demo-start'),
    'demo-booking-98421'
);
$session = $client->getSession(DemoTransport::SESSION_ID);
$extended = $client->extendSession(
    DemoTransport::SESSION_ID,
    DemoTransport::EXTEND_AT,
    GamingControllerClient::newIdempotencyKey('demo-extend')
);
$ended = $client->endSession(
    DemoTransport::SESSION_ID,
    GamingControllerClient::newIdempotencyKey('demo-end')
);

echo "demo_mode local_canned_responses\n";
echo 'health ' . $health['status'] . "\n";
echo 'devices ' . count($devices['items']) . ' connectivity=' . $devices['items'][0]['status']['connectivity'] . "\n";
echo 'create outcome=' . $created['outcome'] . " http_meaning=stored_not_unlocked\n";
echo 'play_confirmed ' . (GamingControllerClient::playConfirmed($session) ? 'true' : 'false') . "\n";
echo 'extend outcome=' . $extended['outcome'] . "\n";
echo 'end outcome=' . $ended['outcome'] . ' lock_confirmed=' . (GamingControllerClient::lockConfirmed($ended) ? 'true' : 'false') . "\n";
echo "demo_never_controls_a_windows_pc\n";
echo "poll_start_confirmed_on_a_lab_controller_before_telling_a_customer_the_pc_is_ready\n";
