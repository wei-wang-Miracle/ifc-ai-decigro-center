package com.ifc.decigro.buskernel.common.context;

import lombok.Data;

/**
 * 用户上下文
 * 用于在线程中传递用户信息
 */
public class UserContext {

    private static final ThreadLocal<String> TENANT_CODE_HOLDER = new ThreadLocal<>();
    private static final ThreadLocal<String> USER_NAME_HOLDER = new ThreadLocal<>();

    public static void setTenantCode(String tenantCode) {
        TENANT_CODE_HOLDER.set(tenantCode);
    }

    public static String getTenantCode() {
        return TENANT_CODE_HOLDER.get();
    }

    public static void setUserName(String username) {
        USER_NAME_HOLDER.set(username);
    }

    public static String getUserName() {
        return USER_NAME_HOLDER.get();
    }

    public static void clear() {
        TENANT_CODE_HOLDER.remove();
        USER_NAME_HOLDER.remove();
    }
}
