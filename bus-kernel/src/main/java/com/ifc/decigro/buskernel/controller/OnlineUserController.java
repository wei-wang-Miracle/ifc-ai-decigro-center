package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.entity.SysLoginLog;
import com.ifc.decigro.buskernel.mapper.SysLoginLogMapper;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

import static com.ifc.decigro.buskernel.entity.table.SysLoginLogTableDef.SYS_LOGIN_LOG;

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
    public List<SysLoginLog> list() {
        return loginLogMapper.selectListByQuery(QueryWrapper.create()
                .select()
                .from(SYS_LOGIN_LOG)
                .where(SYS_LOGIN_LOG.IS_ENABLED.eq(true))
                .orderBy(SYS_LOGIN_LOG.LOGIN_TIME.desc()));
    }

    /**
     * 强退用户
     * 将有效状态 isEnabled 置为 false
     */
    @PostMapping("/kickout/{tokenSign}")
    public void kickout(@PathVariable String tokenSign) {
        SysLoginLog loginLog = new SysLoginLog();
        loginLog.setTokenSign(tokenSign);
        loginLog.setIsEnabled(false);
        loginLogMapper.update(loginLog);
    }
}
