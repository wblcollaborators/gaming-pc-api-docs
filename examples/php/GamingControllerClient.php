<?php

declare(strict_types=1);

/**
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Weblytic Labs
 * See ../../LICENSE-EXAMPLES-MIT.md
 *
 * HTTPS JSON client for the Universal Gaming PC Agent Controller.
 *
 * Booking applications obtain an OAuth 2.0 access token from the operator
 * identity provider. This class does not mint tokens and does not call
 * agent mTLS routes. Python, PHP, and cURL use the same paths and schemas.
 */
final class GamingControllerClient
{
    public const HEALTH_PATH = '/api/v1/health';
    public const DEVICES_PATH = '/api/v1/devices';
    public const SESSIONS_PATH = '/api/v1/sessions';
    public const IDEMPOTENCY_KEY_PATTERN = '/^[A-Za-z0-9._:-]{8,128}$/';
    public const EXPIRES_AT_PATTERN = '/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/';

    private string $baseUrl;
    private string $accessToken;
    private int $timeoutSeconds;
    /** @var callable|null */
    private $transport;

    public function __construct(string $baseUrl, string $accessToken, int $timeoutSeconds = 30, ?callable $transport = null)
    {
        $parts = parse_url($baseUrl);
        if (!is_array($parts) || empty($parts['scheme']) || empty($parts['host'])) {
            throw new InvalidArgumentException('base_url must be an absolute http(s) URL');
        }
        $scheme = strtolower((string) $parts['scheme']);
        $host = strtolower((string) $parts['host']);
        if ($scheme === 'http' && !in_array($host, ['127.0.0.1', 'localhost'], true)) {
            throw new InvalidArgumentException('non-loopback controller URLs must use https');
        }
        if ($scheme !== 'https' && $scheme !== 'http') {
            throw new InvalidArgumentException('base_url must be an absolute http(s) URL');
        }
        if ($accessToken === '') {
            throw new InvalidArgumentException('access_token is required');
        }
        $port = isset($parts['port']) ? ':' . $parts['port'] : '';
        $this->baseUrl = $scheme . '://' . $parts['host'] . $port;
        $this->accessToken = $accessToken;
        $this->timeoutSeconds = $timeoutSeconds;
        $this->transport = $transport;
    }

    public function __debugInfo(): array
    {
        return [
            'baseUrl' => $this->baseUrl,
            'timeoutSeconds' => $this->timeoutSeconds,
        ];
    }

    public static function newIdempotencyKey(string $prefix = 'booking'): string
    {
        $key = $prefix . '-' . bin2hex(random_bytes(8));
        if (preg_match(self::IDEMPOTENCY_KEY_PATTERN, $key) !== 1) {
            throw new RuntimeException('generated Idempotency-Key does not match the required pattern');
        }
        return $key;
    }

    /**
     * @param array<string, mixed> $payload
     * @return array<string, mixed>
     */
    public static function sessionDocument(array $payload): array
    {
        if (isset($payload['session']) && is_array($payload['session']) && isset($payload['session']['session_id'])) {
            return $payload['session'];
        }
        return $payload;
    }

    /** @param array<string, mixed> $payload */
    public static function playConfirmed(array $payload): bool
    {
        return self::sessionDocument($payload)['start_confirmed'] === true;
    }

    /** @param array<string, mixed> $payload */
    public static function lockConfirmed(array $payload): bool
    {
        return self::sessionDocument($payload)['lock_confirmed'] === true;
    }

    /** @return array<string, mixed> */
    public function health(): array
    {
        return $this->request('GET', self::HEALTH_PATH, null, null, false);
    }

    /**
     * @return array<string, mixed>
     */
    public function listDevices(
        ?int $limit = null,
        ?string $cursor = null,
        ?string $platform = null,
        ?string $connectivity = null
    ): array {
        $query = [];
        if ($limit !== null) {
            $query['limit'] = (string) $limit;
        }
        if ($cursor !== null) {
            $query['cursor'] = $cursor;
        }
        if ($platform !== null) {
            $query['platform'] = $platform;
        }
        if ($connectivity !== null) {
            $query['connectivity'] = $connectivity;
        }
        $path = self::DEVICES_PATH;
        if ($query !== []) {
            $path .= '?' . http_build_query($query);
        }
        return $this->request('GET', $path);
    }

    /**
     * @return array<string, mixed>
     */
    public function createSession(
        string $deviceId,
        string $expiresAt,
        string $idempotencyKey,
        ?string $externalReference = null
    ): array {
        $body = [
            'device_id' => self::uuid($deviceId, 'device_id'),
            'expires_at' => self::expiresAt($expiresAt),
        ];
        if ($externalReference !== null) {
            $body['external_reference'] = $externalReference;
        }
        return $this->request('POST', self::SESSIONS_PATH, $body, $idempotencyKey);
    }

    /** @return array<string, mixed> */
    public function getSession(string $sessionId): array
    {
        return $this->request('GET', self::SESSIONS_PATH . '/' . self::uuid($sessionId, 'session_id'));
    }

    /** @return array<string, mixed> */
    public function extendSession(string $sessionId, string $expiresAt, string $idempotencyKey): array
    {
        return $this->request(
            'POST',
            self::SESSIONS_PATH . '/' . self::uuid($sessionId, 'session_id') . '/extend',
            ['expires_at' => self::expiresAt($expiresAt)],
            $idempotencyKey
        );
    }

    /** @return array<string, mixed> */
    public function endSession(string $sessionId, string $idempotencyKey, ?string $reason = 'user_request'): array
    {
        $body = $reason === null ? null : ['reason' => $reason];
        return $this->request(
            'POST',
            self::SESSIONS_PATH . '/' . self::uuid($sessionId, 'session_id') . '/end',
            $body,
            $idempotencyKey
        );
    }

    /**
     * @param array<string, mixed>|null $jsonBody
     * @return array<string, mixed>
     */
    private function request(
        string $method,
        string $path,
        ?array $jsonBody = null,
        ?string $idempotencyKey = null,
        bool $auth = true
    ): array {
        if ($method !== strtoupper($method) || !in_array($method, ['GET', 'POST'], true)) {
            throw new InvalidArgumentException('method must be GET or POST in uppercase');
        }
        $headers = ['Accept: application/json'];
        $payload = null;
        if ($jsonBody !== null) {
            $encoded = json_encode($jsonBody, JSON_UNESCAPED_SLASHES);
            if ($encoded === false) {
                throw new RuntimeException('request JSON could not be encoded');
            }
            $payload = $encoded;
            $headers[] = 'Content-Type: application/json';
        }
        if ($auth) {
            $headers[] = 'Authorization: Bearer ' . $this->accessToken;
        }
        if ($idempotencyKey !== null) {
            if (preg_match(self::IDEMPOTENCY_KEY_PATTERN, $idempotencyKey) !== 1) {
                throw new InvalidArgumentException('Idempotency-Key does not match the required pattern');
            }
            $headers[] = 'Idempotency-Key: ' . $idempotencyKey;
        }

        if ($this->transport !== null) {
            [$status, $ignoredHeaders, $raw] = ($this->transport)(
                $method,
                $this->baseUrl . $path,
                $headers,
                $payload,
                $this->timeoutSeconds
            );
            unset($ignoredHeaders);
        } else {
            $curl = curl_init($this->baseUrl . $path);
            if ($curl === false) {
                throw new RuntimeException('cURL could not start');
            }
            curl_setopt_array($curl, [
                CURLOPT_CUSTOMREQUEST => $method,
                CURLOPT_HTTPHEADER => $headers,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT => $this->timeoutSeconds,
                CURLOPT_SSL_VERIFYPEER => true,
                CURLOPT_SSL_VERIFYHOST => 2,
            ]);
            if ($payload !== null) {
                curl_setopt($curl, CURLOPT_POSTFIELDS, $payload);
            }
            $raw = curl_exec($curl);
            if ($raw === false) {
                $message = curl_error($curl);
                curl_close($curl);
                throw new ControllerApiError(0, 'network_error', 'The controller could not be reached.', null, [], ['reason' => $message]);
            }
            $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
            curl_close($curl);
        }
        $decoded = json_decode((string) $raw, true);
        if ($status >= 200 && $status < 300) {
            if (!is_array($decoded)) {
                throw new ControllerApiError($status, 'invalid_response', 'The controller response is not a JSON object.', null, [], $decoded);
            }
            return $decoded;
        }
        throw ControllerApiError::fromBody($status, is_array($decoded) ? $decoded : ['raw' => $raw]);
    }

    private static function uuid(string $value, string $field): string
    {
        if (preg_match('/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/', $value) !== 1) {
            throw new InvalidArgumentException($field . ' must be a UUID');
        }
        return strtolower($value);
    }

    private static function expiresAt(string $value): string
    {
        if (preg_match(self::EXPIRES_AT_PATTERN, $value) !== 1) {
            throw new InvalidArgumentException('expires_at must be UTC ISO 8601 with a Z suffix');
        }
        return $value;
    }
}

final class ControllerApiError extends RuntimeException
{
    /** @var list<array<string, mixed>> */
    public array $details;
    public mixed $body;

    /**
     * @param list<array<string, mixed>> $details
     */
    public function __construct(
        public int $statusCode,
        public string $errorCode,
        string $message,
        public ?string $requestId,
        array $details,
        mixed $body
    ) {
        parent::__construct(sprintf('HTTP %d %s: %s', $statusCode, $errorCode, $message));
        $this->details = $details;
        $this->body = $body;
    }

    /** @param array<string, mixed> $payload */
    public static function fromBody(int $status, array $payload): self
    {
        $error = $payload['error'] ?? null;
        if (is_array($error)) {
            $details = $error['details'] ?? [];
            if (!is_array($details)) {
                $details = [];
            }
            return new self(
                $status,
                (string) ($error['code'] ?? 'unknown_error'),
                (string) ($error['message'] ?? 'The controller rejected the request.'),
                isset($error['request_id']) ? (string) $error['request_id'] : null,
                $details,
                $payload
            );
        }
        return new self($status, 'unexpected_error', 'The controller returned a non-JSON error.', null, [], $payload);
    }

    public function isRetryable(): bool
    {
        return $this->statusCode === 503
            || $this->statusCode === 429
            || $this->errorCode === 'storage_unavailable'
            || $this->errorCode === 'rate_limited';
    }
}
