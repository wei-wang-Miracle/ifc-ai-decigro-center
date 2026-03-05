package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.common.api.Result;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 通用工具控制器
 * 功能: 提供与具体业务无关的公共查询接口，如时间、系统状态等
 */
@RestController
@RequestMapping("/common")
public class CommonController {

    private static final DateTimeFormatter FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /**
     * 获取服务器当前时间
     * 返回: 格式化的当前日期时间字符串及时间戳
     */
    @ToolCard(
        tool_name    = "get_current_time",
        summary      = "获取当前时间",
        alias        = "查询服务器时间",
        description  = "获取服务器当前的精确日期和时间。"
                     + "适用场景：当用户询问\"现在几点\"、\"今天是几号\"、\"当前日期\"等与时间相关的问题时调用。"
                     + "约束：本工具不接受任何参数，始终返回服务端系统时间，不代表用户本地时区。",
        tags         = { "common", "time", "utility" },
        privileges   = "public",
        input_examples  = "{}",
        output_examples = "{\"datetime\":\"2025-08-01 14:30:00\",\"timestamp\":1754038200000}"
    )
    @PostMapping("/get_current_time")
    public Result<Map<String, Object>> getCurrentTime() {
        LocalDateTime now = LocalDateTime.now();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("datetime", now.format(FORMATTER));
        data.put("timestamp", System.currentTimeMillis());
        return Result.success(data);
    }
}
