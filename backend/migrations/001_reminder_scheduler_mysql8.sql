ALTER TABLE reminders
    MODIFY COLUMN status VARCHAR(11) NOT NULL DEFAULT 'PENDING',
    DROP CHECK reminder_status,
    ADD CONSTRAINT reminder_status CHECK (
        status IN (
            'PENDING',
            'PROCESSING',
            'AUDIO_READY',
            'FAILED',
            'COMPLETED',
            'CANCELLED'
        )
    );

ALTER TABLE reminder_logs
    MODIFY COLUMN event_type VARCHAR(15) NOT NULL,
    DROP CHECK reminder_event_type,
    ADD CONSTRAINT reminder_event_type CHECK (
        event_type IN (
            'CREATED',
            'TRIGGERED',
            'AUDIO_GENERATED',
            'DELIVERED',
            'PLAYED',
            'COMPLETED',
            'FAILED'
        )
    );

CREATE TABLE reminder_occurrences (
    id INTEGER NOT NULL AUTO_INCREMENT,
    reminder_id INTEGER NOT NULL,
    occurrence_at DATETIME NOT NULL,
    status VARCHAR(10) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at DATETIME NULL,
    audio_file_path VARCHAR(500) NULL,
    generated_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_reminder_occurrence_time UNIQUE (reminder_id, occurrence_at),
    CONSTRAINT ck_reminder_occurrences_attempt_count
        CHECK (attempt_count >= 0 AND attempt_count <= 3),
    CONSTRAINT reminder_occurrence_status CHECK (
        status IN (
            'PENDING',
            'PROCESSING',
            'AUDIO_READY',
            'FAILED',
            'COMPLETED',
            'CANCELLED'
        )
    ),
    CONSTRAINT fk_reminder_occurrences_reminder
        FOREIGN KEY (reminder_id) REFERENCES reminders (id) ON DELETE CASCADE,
    INDEX ix_reminder_occurrences_status_retry (status, next_retry_at),
    INDEX ix_reminder_occurrences_reminder_status (reminder_id, status)
) ENGINE=InnoDB;