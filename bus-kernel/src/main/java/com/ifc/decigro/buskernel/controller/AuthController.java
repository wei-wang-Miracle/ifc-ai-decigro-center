package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.dto.LoginRequest;
import com.ifc.decigro.buskernel.service.SysUserService;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 认证控制器
 * 功能: 处理登录、登出等安全相关请求
 */
@Slf4j
@RestController
@RequestMapping("/auth")
public class AuthController {

    @Autowired
    private SysUserService userService;

    /**
     * 用户登录
     * 参数: 登录请求对象 (username, password)
     * 返回: 包含 token 和用户信息的统一响应对象
     */
    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody LoginRequest request, HttpServletRequest httpRequest,
            HttpServletResponse response) {
        log.info("用户登录请求: {}", request.getUsername());
        Map<String, Object> loginResult = userService.login(request, httpRequest);
        String token = (String) loginResult.get("token");

        // 设置 Cookie
        Cookie cookie = new Cookie("token", token);
        cookie.setPath("/");
        cookie.setHttpOnly(true);
        response.addCookie(cookie);

        // 设置自定义 Header，供前端请求拦截器使用
        response.setHeader("X-Auth-Token", token);

        return Result.success(loginResult);
    }

    /**
     * 用户主动登出
     * 功能: 使当前 Token 失效
     * 返回: 成功标志
     */
    @PostMapping("/logout")
    public Result<Void> logout(HttpServletRequest httpRequest) {
        String token = httpRequest.getHeader("X-Auth-Token");
        userService.logout(token);
        return Result.success();
    }
}
