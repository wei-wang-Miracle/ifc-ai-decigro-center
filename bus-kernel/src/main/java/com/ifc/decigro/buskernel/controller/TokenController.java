package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.auth.TokenProvider;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * Token 解析控制器
 * 功能: 提供 Token 解析接口，供 AI Engine 调用获取用户信息
 */
@Slf4j
@RestController
@RequestMapping("/token")
public class TokenController {

    @Autowired
    private TokenProvider tokenProvider;

    /**
     * 解析 Token，返回用户信息
     * 路径: GET /api/dg/token/parse
     * 参数: X-Auth-Token Header
     * 返回: 包含 tenant_code, dept_id, username, user_id 的 Map
     */
    @GetMapping("/parse")
    public Result<Map<String, String>> parseToken(
            @RequestHeader("X-Auth-Token") String token) {
        try {
            // 调用 TokenProvider 验证并解析 Token
            // 返回格式: [Prefix, TenantCode, DeptId, UserName, Timestamp]
            String[] parts = tokenProvider.validateAndParse(token);

            Map<String, String> result = new HashMap<>();
            result.put("tenant_code", parts[1]);
            result.put("dept_id", parts[2]);
            result.put("username", parts[3]);
            result.put("user_id", parts[3]); // username 作为 user_id
            result.put("timestamp", parts[4]);

            log.info("Token 解析成功: user_id={}", parts[3]);
            return Result.success(result);
        } catch (IllegalArgumentException e) {
            log.warn("Token 解析失败: {}", e.getMessage());
            return Result.fail(401, "Token 无效: " + e.getMessage());
        }
    }
}
