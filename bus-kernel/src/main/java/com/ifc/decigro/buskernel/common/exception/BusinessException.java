package com.ifc.decigro.buskernel.common.exception;

import lombok.Getter;

/**
 * 功能: 自定义业务异常类。
 * 用于区分系统故障和可预见的业务逻辑错误（如参数错误、余额不足等）。
 */
@Getter
public class BusinessException extends RuntimeException {

    /**
     * 错误码 (默认 500)
     */
    private final int code;

    /**
     * 功能: 构造函数。
     * 参数: message 异常提示信息
     */
    public BusinessException(String message) {
        this(500, message);
    }

    /**
     * 功能: 构造函数 (含代码)。
     * 参数: code 错误码
     * 参数: message 异常提示信息
     */
    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
    }
}
