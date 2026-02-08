package com.ifc.decigro.buskernel.common.interceptor;

import com.ifc.decigro.buskernel.common.auth.TokenProvider;
import com.ifc.decigro.buskernel.common.context.UserContext;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import com.ifc.decigro.buskernel.entity.SysLoginLog;
import com.ifc.decigro.buskernel.mapper.SysLoginLogMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 统一拦截器
 * 负责 Token 解析、上下文注入、链路追踪
 */
@Component
public class AuthInterceptor implements HandlerInterceptor {

    @Autowired
    private TokenProvider tokenProvider;

    @Autowired
    private SysLoginLogMapper loginLogMapper;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        String token = request.getHeader("X-Auth-Token");

        // Allow public endpoints (Simple implementation, ideally use security config or
        // annotations)
        if (request.getRequestURI().contains("/auth/login")) {
            return true;
        }

        if (token != null) {
            try {
                // Parse Token: [Prefix, TenantCode, DeptId, UserName, Timestamp]
                String[] parts = tokenProvider.validateAndParse(token);

                String tenantCode = parts[1];
                String userId = parts[2]; // DeptId or UserId depending on implementation, PRD says "DeptId" but implies
                                          // User context
                String username = parts[3];

                // Check if token is still enabled in sys_login_log
                int lastIdx = token.lastIndexOf("_");
                String tokenSign = token.substring(lastIdx + 1);
                SysLoginLog loginLog = loginLogMapper.selectOneById(tokenSign);
                if (loginLog == null || !loginLog.getIsEnabled()) {
                    response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                    return false;
                }

                // Set Context
                UserContext.setTenantCode(tenantCode);
                UserContext.setUserName(username);

                // Set MDC for Logging
                MDC.put("tenant", tenantCode);
                MDC.put("user", username);

                return true;
            } catch (Exception e) {
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                return false;
            }
        }

        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        return false;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex)
            throws Exception {
        UserContext.clear();
        MDC.clear();
    }
}
