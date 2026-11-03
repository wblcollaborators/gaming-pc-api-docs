<?php

declare(strict_types=1);

/**
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Weblytic Labs
 * See ../../LICENSE-EXAMPLES-MIT.md
 */

require_once __DIR__ . '/GamingControllerClient.php';
require_once __DIR__ . '/DemoTransport.php';

function assert_true(bool $condition, string $message): void
{
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$session = [
    'outcome' => 'accepted',
    'session' => [
        'session_id' => '33333333-3333-4333-8333-333333333333',
        'status' => 'accepted',
        'start_confirmed' => false,
        'lock_confirmed' => false,
    ],
];

assert_true(GamingControllerClient::sessionDocument($session)['session_id'] === '33333333-3333-4333-8333-333333333333', 'POST session unwrap failed');
assert_true(GamingControllerClient::playConfirmed($session) === false, 'unconfirmed play must be false');
assert_true(GamingControllerClient::lockConfirmed($session) === false, 'unconfirmed lock must be false');
assert_true(GamingControllerClient::playConfirmed(['start_confirmed' => true, 'lock_confirmed' => false]) === true, 'GET play flag failed');
assert_true(preg_match(GamingControllerClient::IDEMPOTENCY_KEY_PATTERN, GamingControllerClient::newIdempotencyKey('booking')) === 1, 'idempotency key pattern failed');

$source = file_get_contents(__DIR__ . '/GamingControllerClient.php');
assert_true(is_string($source) && str_contains($source, '/api/v1/health'), 'health path missing');
assert_true(str_contains($source, '/api/v1/devices'), 'devices path missing');
assert_true(str_contains($source, '/api/v1/sessions'), 'sessions path missing');
assert_true(!str_contains($source, '/api/v1/commands/'), 'PHP client must not call getCommand');
assert_true(!str_contains($source, '/api/v1/agents/heartbeat'), 'PHP client must not call heartbeat');

$error = new ControllerApiError(403, 'forbidden', 'The token does not include the required scope.', 'req-1', [], []);
assert_true($error->isRetryable() === false, '403 must not be retryable');
$retry = new ControllerApiError(503, 'storage_unavailable', 'Storage is unavailable.', 'req-1', [], []);
assert_true($retry->isRetryable() === true, '503 must be retryable');
$limited = new ControllerApiError(429, 'rate_limited', 'The account exceeded the request rate limit.', 'req-1', [], []);
assert_true($limited->isRetryable() === true, '429 must be retryable');
$unauthorized = new ControllerApiError(401, 'unauthorized', 'The bearer token is not valid.', 'req-1', [], []);
assert_true($unauthorized->isRetryable() === false, '401 must not be retryable');
$missing = new ControllerApiError(404, 'session_not_found', 'The session is not in this account.', 'req-1', [], []);
assert_true($missing->isRetryable() === false, '404 must not be retryable');

$demo = new DemoTransport();
$client = new GamingControllerClient('https://controller.example', 'demo-access-token-not-a-credential', 30, $demo);
$created = $client->createSession(DemoTransport::DEVICE_ID, DemoTransport::EXPIRES_AT, 'demo-start-key');
assert_true($created['outcome'] === 'accepted', 'demo create outcome');
assert_true(GamingControllerClient::playConfirmed($created) === false, 'demo must not confirm play');
$ended = $client->endSession(DemoTransport::SESSION_ID, 'demo-end-key');
assert_true(GamingControllerClient::lockConfirmed($ended) === false, 'demo must not confirm lock');
foreach ($demo->calls as $call) {
    assert_true($call[1] !== '/api/v1/agents/heartbeat', 'demo must not call heartbeat');
}

fwrite(STDOUT, "php client contract checks passed\n");
