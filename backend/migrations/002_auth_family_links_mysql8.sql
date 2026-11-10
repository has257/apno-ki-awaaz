ALTER TABLE users
    ADD COLUMN password_hash VARCHAR(255) NULL;

CREATE TABLE family_elderly_links (
    id INTEGER NOT NULL AUTO_INCREMENT,
    family_user_id INTEGER NOT NULL,
    elderly_user_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_family_elderly_link_pair
        UNIQUE (family_user_id, elderly_user_id),
    CONSTRAINT ck_family_elderly_links_not_self
        CHECK (family_user_id <> elderly_user_id),
    CONSTRAINT family_elderly_link_status
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'REVOKED')),
    CONSTRAINT fk_family_elderly_links_family
        FOREIGN KEY (family_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_family_elderly_links_elderly
        FOREIGN KEY (elderly_user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX ix_family_elderly_links_family_status (family_user_id, status),
    INDEX ix_family_elderly_links_elderly_status (elderly_user_id, status)
) ENGINE=InnoDB;