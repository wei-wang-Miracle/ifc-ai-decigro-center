package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.entity.SysUser;
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

@Slf4j
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @Autowired
    private SysUserService userService;

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody LoginRequest request, HttpServletRequest httpRequest,
            HttpServletResponse response) {
        Map<String, Object> result = userService.login(request, httpRequest);
        String token = (String) result.get("token");

        // Set Cookie and Header
        Cookie cookie = new Cookie("token", token);
        cookie.setPath("/");
        cookie.setHttpOnly(true);
        // cookie.setSecure(true); // Enable in production
        response.addCookie(cookie);
        response.setHeader("X-Auth-Token", token);

        return result;
    }

    /**
     * 用户主动登出
     * 功能: 将当前请求使用的 Token 在数据库中标记为禁用
     */
    @PostMapping("/logout")
    public void logout(HttpServletRequest httpRequest) {
        String token = httpRequest.getHeader("X-Auth-Token");
        userService.logout(token);
    }
}
