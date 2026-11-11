
CREATE TABLE IF NOT EXISTS profile (
    id               TEXT    NOT NULL PRIMARY KEY,
    created_at       INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS device_info (
    id               TEXT    NOT NULL PRIMARY KEY,
    profile_id       TEXT    ,
    name             TEXT    NOT NULL,
    fingerprint      TEXT    NOT NULL,
    public_key       TEXT    NOT NULL UNIQUE,
    platform         TEXT    NOT NULL,
    status           TEXT    NOT NULL,
    created_at       INTEGER    NOT NULL DEFAULT (unixepoch()),
    FOREIGN KEY (profile_id) REFERENCES profile(id),
    CHECK (platform IN ('desktop', 'android', 'ios')),
    CHECK (status IN ('active', 'revoked'))
);

CREATE TABLE IF NOT EXISTS pairing_request (
    id              TEXT    NOT NULL PRIMARY KEY,
    device_1_id     TEXT    NOT NULL,
    device_2_id     TEXT,
    status          TEXT    NOT NULL,
    token_hashed    TEXT    NOT NULL UNIQUE,
    created_at      INTEGER    NOT NULL DEFAULT (unixepoch()),
    expires_at      INTEGER    NOT NULL,

    FOREIGN KEY (device_1_id) REFERENCES device_info(id),
    FOREIGN KEY (device_2_id) REFERENCES device_info(id),
    CHECK (status IN ('pending', 'accepted', 'rejected'))
);


CREATE TABLE IF NOT EXISTS device_pair (
    id           TEXT NOT NULL PRIMARY KEY,
    device_1_id  TEXT NOT NULL,
    device_2_id  TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   INTEGER NOT NULL DEFAULT (unixepoch()),

    FOREIGN KEY (device_1_id) REFERENCES device_info(id),
    FOREIGN KEY (device_2_id) REFERENCES device_info(id),
    
    CHECK (device_1_id < device_2_id),
    CHECK (device_1_id <> device_2_id),
    CHECK (status IN ('active', 'revoked')),
    UNIQUE (device_1_id, device_2_id)
);

CREATE TABLE IF NOT EXISTS auth_challenge (
    challenge    TEXT NOT NULL PRIMARY KEY,
    device_id    TEXT NOT NULL,
    created_at   INTEGER NOT NULL DEFAULT (unixepoch()),
    expires_at   INTEGER NOT NULL DEFAULT (unixepoch() + 60),

    FOREIGN KEY (device_id) REFERENCES device_info(id)
);


CREATE TABLE IF NOT EXISTS session (
    id              TEXT NOT NULL PRIMARY KEY,
    token_hashed    TEXT NOT NULL UNIQUE,
    device_id       TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
    expires_at      INTEGER  NOT NULL DEFAULT (unixepoch() + 24 * 3600),

    FOREIGN KEY (device_id) REFERENCES device_info(id),
    CHECK (status IN ('active', 'revoked'))
);


CREATE TABLE IF NOT EXISTS file (
    id              TEXT NOT NULL PRIMARY KEY,
    sender_id       TEXT NOT NULL,
    receiver_id       TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    object_key      TEXT NOT NULL UNIQUE,
    size            INTEGER NOT NULL,
    content_type    TEXT NOT NULL,
    checksum        TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch()),

    FOREIGN KEY (sender_id)   REFERENCES device_info(id),
    FOREIGN KEY (receiver_id) REFERENCES device_info(id),
    CHECK (status IN ('pending', 'uploaded', 'downloaded', 'deleted'))
);