<?php

declare(strict_types=1);

/**
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Weblytic Labs
 * See ../../LICENSE-EXAMPLES-MIT.md
 *
 * Copy-paste usage for Laravel or plain PHP.
 *
 * This file is not a Laravel package and does not change booking models.
 * Obtain the access token from the operator identity provider, then call the
 * same HTTPS contract that Python and cURL use.
 */

require_once __DIR__ . '/GamingControllerClient.php';

function futureDeadline(int $minutes = 60): string
{
    return gmdate('Y-m-d\TH:i:s\Z', time() + ($minutes * 60));
}

function startPlay(
    string $controllerUrl,
    string $accessToken,
    string $deviceId,
    string $bookingReference,
    int $minutes = 60
): array {
    $client = new GamingControllerClient($controllerUrl, $accessToken);
    $created = $client->createSession(
        $deviceId,
        futureDeadline($minutes),
        GamingControllerClient::newIdempotencyKey($bookingReference),
        $bookingReference
    );
    $session = GamingControllerClient::sessionDocument($created);
    // Persist session_id, command_id, and the Idempotency-Key on the existing booking row.
    return [
        'session_id' => $session['session_id'],
        'status' => $session['status'],
        'play_confirmed' => GamingControllerClient::playConfirmed($created),
        'outcome' => $created['outcome'],
    ];
}

function waitForPlay(GamingControllerClient $client, string $sessionId): array
{
    $session = $client->getSession($sessionId);
    return [
        'status' => $session['status'],
        'play_confirmed' => GamingControllerClient::playConfirmed($session),
    ];
}

function addTime(GamingControllerClient $client, string $sessionId, int $extraMinutes): array
{
    return $client->extendSession(
        $sessionId,
        futureDeadline($extraMinutes),
        GamingControllerClient::newIdempotencyKey('extend')
    );
}

function stopPlay(GamingControllerClient $client, string $sessionId): array
{
    $ended = $client->endSession($sessionId, GamingControllerClient::newIdempotencyKey('end'));
    $session = $client->getSession($sessionId);
    return [
        'outcome' => $ended['outcome'],
        'status' => $session['status'],
        'lock_confirmed' => GamingControllerClient::lockConfirmed($session),
    ];
}

function handleControllerError(ControllerApiError $exc): string
{
    if ($exc->isRetryable()) {
        return 'retry_same_idempotency_key';
    }
    if (in_array($exc->statusCode, [401, 403], true)) {
        return 'authorization_failed';
    }
    return $exc->errorCode;
}
