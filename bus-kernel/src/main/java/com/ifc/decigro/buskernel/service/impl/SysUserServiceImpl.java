package com.ifc.decigro.buskernel.service.impl;

import cn.hutool.crypto.digest.BCrypt;
import com.ifc.decigro.buskernel.common.auth.TokenProvider;
import com.ifc.decigro.buskernel.common.exception.BusinessException;
import com.ifc.decigro.buskernel.common.crypto.RsaUtils;
import com.ifc.decigro.buskernel.entity.SysLoginLog;
import com.ifc.decigro.buskernel.entity.SysUser;
import com.ifc.decigro.buskernel.entity.dto.LoginRequest;
import com.ifc.decigro.buskernel.mapper.SysLoginLogMapper;
import com.ifc.decigro.buskernel.mapper.SysUserMapper;
import com.ifc.decigro.buskernel.service.SysUserService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static com.ifc.decigro.buskernel.entity.table.SysUserTableDef.SYS_USER;

@Slf4j
@Service
public class SysUserServiceImpl implements SysUserService {

    @Autowired
    private SysUserMapper userMapper;

    @Autowired
    private TokenProvider tokenProvider;

    @Autowired
    private SysLoginLogMapper loginLogMapper;

    @Autowired
    private RsaUtils rsaUtils;

    @Override
    public Map<String, Object> login(LoginRequest request, HttpServletRequest httpRequest) {
        String password = rsaUtils.decrypt(request.getPassword());
        SysUser user = userMapper.selectOneByQuery(QueryWrapper.create()
                .select()
                .from(SYS_USER)
                .where(SYS_USER.USERNAME.eq(request.getUsername())));

        if (user == null) {
            log.error("登录失败：未找到用户名为 {} 的用户", request.getUsername());
            throw new BusinessException("用户名或密码错误");
        }

        // 使用 BCrypt 校验密码 (目前先支持明文兼容，后续全量切换)
        if (!checkPassword(password, user.getPassword())) {
            throw new BusinessException("用户名或密码错误");
        }

        if (!user.getIsEnabled()) {
            throw new BusinessException("账户已被禁用，请联系管理员");
        }

        String tenantCode = "HEYI";
        String deptId = user.getDeptId() != null ? user.getDeptId().toString() : "0";
        String token = tokenProvider.createToken(tenantCode, deptId, user.getUsername());

        // 记录登录日志
        SysLoginLog loginLog = new SysLoginLog();
        int lastIdx = token.lastIndexOf("_");
        loginLog.setTokenSign(token.substring(lastIdx + 1));
        loginLog.setUsername(user.getUsername());
        loginLog.setIpAddress(httpRequest.getRemoteAddr());
        loginLog.setLoginTime(LocalDateTime.now());
        loginLog.setIsEnabled(true);
        loginLog.setTenantCode(tenantCode);
        loginLogMapper.insert(loginLog);

        Map<String, Object> result = new HashMap<>();
        result.put("token", token);
        result.put("user", user);
        return result;
    }

    private boolean checkPassword(String inputPassword, String dbPassword) {
        // 兼容模式：如果是 BCrypt 格式则用 BCrypt 校验，否则用等值校验（用于迁移期）
        try {
            if (dbPassword.startsWith("$2a$") || dbPassword.startsWith("$2b$")) {
                return BCrypt.checkpw(inputPassword, dbPassword);
            }
        } catch (Exception e) {
            log.warn("BCrypt 校验失败，尝试等值校验");
        }
        return inputPassword.equals(dbPassword);
    }

    @Override
    public void logout(String token) {
        if (token != null) {
            int lastIdx = token.lastIndexOf("_");
            String tokenSign = token.substring(lastIdx + 1);
            SysLoginLog loginLog = loginLogMapper.selectOneById(tokenSign);
            if (loginLog != null) {
                loginLog.setIsEnabled(false);
                loginLogMapper.update(loginLog);
            }
        }
    }

    @Override
    public List<SysUser> list() {
        return userMapper.selectAll();
    }

    @Override
    @Transactional
    public void saveOrUpdate(SysUser user) {
        if (user.getId() == null) {
            // 新建用户，密码解密并哈希处理
            if (user.getPassword() != null) {
                String rawPassword = rsaUtils.decrypt(user.getPassword());
                user.setPassword(BCrypt.hashpw(rawPassword, BCrypt.gensalt()));
            }
            userMapper.insert(user);
        } else {
            // 更新用户，如果包含密码字段且被修改，则重新哈希
            if (user.getPassword() != null && !user.getPassword().startsWith("$2a$")) {
                String rawPassword = rsaUtils.decrypt(user.getPassword());
                user.setPassword(BCrypt.hashpw(rawPassword, BCrypt.gensalt()));
            }
            userMapper.update(user);
        }
    }

    @Override
    public void deleteById(Long id) {
        userMapper.deleteById(id);
    }

    @Override
    public SysUser getByUsername(String username) {
        return userMapper.selectOneByQuery(QueryWrapper.create()
                .select()
                .from(SYS_USER)
                .where(SYS_USER.USERNAME.eq(username)));
    }

    @Override
    @Transactional
    public void updatePassword(String username, String oldPassword, String newPassword) {
        SysUser user = getByUsername(username);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }

        String rawOldPassword = rsaUtils.decrypt(oldPassword);
        String rawNewPassword = rsaUtils.decrypt(newPassword);

        if (!checkPassword(rawOldPassword, user.getPassword())) {
            throw new BusinessException("旧密码错误");
        }

        user.setPassword(BCrypt.hashpw(rawNewPassword, BCrypt.gensalt()));
        userMapper.update(user);
    }

    @Override
    @Transactional
    public void updateProfile(String username, com.ifc.decigro.buskernel.dto.ProfileUpdateRequest request) {
        SysUser user = getByUsername(username);
        if (user != null) {
            user.setNickName(request.getNickName());
            user.setGender(request.getGender());
            user.setEmail(request.getEmail());
            user.setPhone(request.getPhone());
            userMapper.update(user);
        }
    }
}
