-- Database Initialization Script for DeciGro Center
-- 1. Create Tables
-- SysTenant
CREATE TABLE IF NOT EXISTS sys_tenant (
    tenant_code VARCHAR(32) PRIMARY KEY,
    tenant_name VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP DEFAULT NOW()
);
-- SysRole
CREATE TABLE IF NOT EXISTS sys_role (
    role_id BIGSERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL,
    role_desc VARCHAR(255),
    tool_list JSONB,
    is_enabled BOOLEAN DEFAULT TRUE
);
-- SysDept
CREATE TABLE IF NOT EXISTS sys_dept (
    dept_id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT,
    dept_name VARCHAR(64) NOT NULL,
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP DEFAULT NOW()
);
-- SysUser
CREATE TABLE IF NOT EXISTS sys_user (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    password_v VARCHAR(64),
    nick_name VARCHAR(64),
    gender INT,
    email VARCHAR(100),
    phone VARCHAR(20),
    avatar_path VARCHAR(255),
    dept_id BIGINT,
    role_id BIGINT,
    tool_list JSONB,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP DEFAULT NOW()
);
-- SysLoginLog
CREATE TABLE IF NOT EXISTS sys_login_log (
    token_sign VARCHAR(64) PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    ip_address VARCHAR(50),
    login_time TIMESTAMP,
    tenant_code VARCHAR(32),
    is_enabled BOOLEAN DEFAULT TRUE,
    created_time TIMESTAMP DEFAULT NOW(),
    updated_time TIMESTAMP DEFAULT NOW()
);
-- 2. Data Initialization
-- Init Tenant
INSERT INTO sys_tenant (tenant_code, tenant_name, is_enabled)
VALUES ('HEYI', '和一集团', TRUE) ON CONFLICT (tenant_code) DO NOTHING;
-- Init Dept
INSERT INTO sys_dept (dept_id, parent_id, dept_name)
VALUES (100, 0, '平台管理部') ON CONFLICT (dept_id) DO NOTHING;
-- Init Role
INSERT INTO sys_role (role_id, role_name, role_desc, is_enabled)
VALUES (1, 'ADMIN', 'Super Administrator', TRUE) ON CONFLICT (role_id) DO NOTHING;
-- Init Admin User
-- Password is 'admin' (In real app, should be encrypted, but PRD asked for reversible encryption or plain for now as per simple auth controller implementation)
INSERT INTO sys_user (
        id,
        username,
        password,
        nick_name,
        dept_id,
        role_id,
        is_enabled
    )
VALUES (1, 'admin', 'admin', 'Super Admin', 100, 1, TRUE) ON CONFLICT (id) DO NOTHING;
-- Reset Sequence
SELECT setval(
        'sys_user_id_seq',
        (
            SELECT MAX(id)
            FROM sys_user
        )
    );
SELECT setval(
        'sys_role_role_id_seq',
        (
            SELECT MAX(role_id)
            FROM sys_role
        )
    );
SELECT setval(
        'sys_dept_dept_id_seq',
        (
            SELECT MAX(dept_id)
            FROM sys_dept
        )
    );
SELECT setval(
        'sys_menu_menu_id_seq',
        (
            SELECT MAX(menu_id)
            FROM sys_menu
        )
    );