package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.SysLoginLog;
import com.ifc.decigro.buskernel.mapper.SysLoginLogMapper;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 在线用户管理控制器
 */
@RestController
@RequestMapping("/api/sys/online")
public class OnlineUserController {

    @Autowired
    private SysLoginLogMapper loginLogMapper;

    /**
     * 获取在线用户列表
     * 仅返回 isEnabled 为 true 的记录
     */
    @GetMapping("/list")
    public Result<List<SysLoginLog>> list() {
        List<SysLoginLog> onlineUsers = loginLogMapper.selectListByQuery(QueryWrapper.create()
                .where("is_enabled = ?", true)
                .orderBy("login_time", false));
        return Result.success(onlineUsers);
    }

    /**
     * 强退用户
     * 将有效状态 isEnabled 置为 false
     */
    @PostMapping("/kickout/{tokenSign}")
    public Result<Void> kickout(@PathVariable String tokenSign) {
        SysLoginLog loginLog = new SysLoginLog();
        loginLog.setTokenSign(tokenSign);
        loginLog.setIsEnabled(false);
        loginLogMapper.update(loginLog);
        return Result.success();
    }
}
