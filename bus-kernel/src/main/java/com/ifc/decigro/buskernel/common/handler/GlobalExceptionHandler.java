package com.ifc.decigro.buskernel.common.handler;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.exception.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import jakarta.servlet.http.HttpServletRequest;

/**
 * 功能: 全局异常处理器。
 * 捕获控制器抛出的所有异常，并将其转换为标准化的 Result 格式返回给前端。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 功能: 捕获自定义业务异常 BusinessException。
     * 参数: e 业务异常对象
     * 返回: 包含错误信息的 Result 对象
     */
    @ExceptionHandler(BusinessException.class)
    public Result<?> handleBusinessException(BusinessException e) {
        log.warn("业务异常: {}", e.getMessage());
        return Result.fail(e.getCode(), e.getMessage());
    }

    /**
     * 功能: 捕获所有其他未预期的系统异常。
     * 参数: e 异常对象
     * 返回: 通用的系统错误 Result 对象
     */
    @ExceptionHandler(Exception.class)
    public Result<?> handleException(Exception e, HttpServletRequest request) {
        log.error("系统异常 [URI: {}]: ", request.getRequestURI(), e);
        return Result.fail(500, "网络繁忙，请稍后再试: " + e.getMessage());
    }
}
