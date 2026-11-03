<?php

declare(strict_types=1);

/**
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Weblytic Labs
 * See ../../LICENSE-EXAMPLES-MIT.md
 *
 * Canned HTTPS responses for local API learning.
 *
 * This transport never contacts a controller, an identity provider, or a
 * Windows PC. HTTP 202 here still means "stored", not unlocked play.
 */
final class DemoTransport
{
    public const DEVICE_ID = '22222222-2222-4222-8222-222222222222';
    public const SESSION_ID = '33333333-3333-4333-8333-333333333333';
    public const COMMAND_ID = '44444444-4444-4444-8444-444444444444';
    public const EXPIRES_AT = '2026-10-30T12:00:00Z';
    public const EXTEND_AT = '2026-10-30T13:00:00Z';

    /** @var list<array{0:string,1:string}> */
    public array $calls = [];

    /**
     * @param array<int, string> $headers
     * @return array{0:int,1:array<string,string>,2:string}
     */
    public function __invoke(string $method, string $url, array $headers, ?string $body, int $timeout): array
    {
        unset($headers, $body, $timeout);
        $path = (string) parse_url($url, PHP_URL_PATH);
        $this->calls[] = [$method, $path];
        if ($method === 'GET' && $path === '/api/v1/health') {
            return $this->ok(200, ['status' => 'ok']);
        }
        if ($method === 'GET' && $path === '/api/v1/devices') {
            return $this->ok(200, [
                'items' => [[
                    'device_id' => self::DEVICE_ID,
                    'display_name' => 'Demo Station',
                    'platform' => 'windows',
                    'status' => [
                        'connectivity' => 'offline',
                        'access_state' => 'unknown',
                        'status_stale' => true,
                    ],
                ]],
                'next_cursor' => null,
            ]);
        }
        if ($method === 'POST' && $path === '/api/v1/sessions') {
            return $this->ok(202, $this->created());
        }
        if ($method === 'GET' && $path === '/api/v1/sessions/' . self::SESSION_ID) {
            return $this->ok(200, $this->created()['session']);
        }
        if ($method === 'POST' && $path === '/api/v1/sessions/' . self::SESSION_ID . '/extend') {
            $payload = $this->created();
            $payload['command']['command_type'] = 'extend_session';
            $payload['session']['pending_expires_at'] = self::EXTEND_AT;
            return $this->ok(202, $payload);
        }
        if ($method === 'POST' && $path === '/api/v1/sessions/' . self::SESSION_ID . '/end') {
            $payload = $this->created();
            $payload['command']['command_type'] = 'end_session';
            $payload['session']['status'] = 'ending';
            return $this->ok(202, $payload);
        }
        $headers = ['Content-Type' => 'application/json', 'X-Request-Id' => '77777777-7777-4777-8777-777777777777'];
        $body = json_encode([
            'error' => [
                'code' => 'not_found',
                'message' => 'The resource was not found.',
                'request_id' => '77777777-7777-4777-8777-777777777777',
                'details' => [],
            ],
        ], JSON_UNESCAPED_SLASHES) ?: '{}';
        return [404, $headers, $body];
    }

    /**
     * @param array<string, mixed> $payload
     * @return array{0:int,1:array<string,string>,2:string}
     */
    private function ok(int $status, array $payload): array
    {
        return [
            $status,
            ['Content-Type' => 'application/json', 'X-Request-Id' => '77777777-7777-4777-8777-777777777777'],
            json_encode($payload, JSON_UNESCAPED_SLASHES) ?: '{}',
        ];
    }

    /**
     * @return array{0:int,1:array<string,string>,2:string}
     */
    public static function cannedError(int $status): array
    {
        $map = [
            401 => ['unauthorized', 'The bearer token is not valid.'],
            403 => ['forbidden', 'The token does not include the required scope.'],
            404 => ['session_not_found', 'The session is not in this account.'],
            429 => ['rate_limited', 'The account exceeded the request rate limit.'],
            503 => ['storage_unavailable', 'Device storage is unavailable.'],
        ];
        [$code, $message] = $map[$status];
        $headers = ['Content-Type' => 'application/json', 'X-Request-Id' => '77777777-7777-4777-8777-777777777777'];
        if ($status === 429) {
            $headers['Retry-After'] = '16';
        }
        $body = json_encode([
            'error' => [
                'code' => $code,
                'message' => $message,
                'request_id' => '77777777-7777-4777-8777-777777777777',
                'details' => [],
            ],
        ], JSON_UNESCAPED_SLASHES) ?: '{}';
        return [$status, $headers, $body];
    }

    /** @return array<string, mixed> */
    private function created(): array
    {
        return [
            'outcome' => 'accepted',
            'session' => [
                'session_id' => self::SESSION_ID,
                'device_id' => self::DEVICE_ID,
                'status' => 'accepted',
                'start_confirmed' => false,
                'lock_confirmed' => false,
                'expires_at' => self::EXPIRES_AT,
            ],
            'command' => [
                'command_id' => self::COMMAND_ID,
                'command_type' => 'start_session',
                'status' => 'pending',
                'device_effect_confirmed' => false,
            ],
        ];
    }
}
