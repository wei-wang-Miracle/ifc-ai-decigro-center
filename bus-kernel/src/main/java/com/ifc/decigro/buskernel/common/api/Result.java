package com.ifc.decigro.buskernel.common.api;

import lombok.Data;

/**
 * 功能: 统一 API 响应包装类。
 * 确保所有接口返回格式一致（code, message, data），方便前端和 AI Agent 解析。
 * 
 * 参数: <T> 响应数据的类型
 */
@Data
public class Result<T> {

    /**
     * 业务响应码 (200: 成功, 其他: 失败)
     */
    private int code;

    /**
     * 响应消息
     */
    private String message;

    /**
     * 响应数据内容
     */
    private T data;

    /**
     * 构造函数 (全参)。
     */
    public Result(int code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
    }

    /**
     * 功能: 快速返回成功响应。
     * 参数: data 返回的数据
     * 返回: Result 对象
     */
    public static <T> Result<T> success(T data) {
        return new Result<>(200, "操作成功", data);
    }

    /**
     * 功能: 快速返回成功响应 (无数据)。
     * 返回: Result 对象
     */
    public static <T> Result<T> success() {
        return success(null);
    }

    /**
     * 功能: 快速返回失败响应。
     * 参数: code 错误码
     * 参数: message 错误信息
     * 返回: Result 对象
     */
    public static <T> Result<T> fail(int code, String message) {
        return new Result<>(code, message, null);
    }

    /**
     * 功能: 快速返回通用失败响应 (500)。
     * 参数: message 错误信息
     * 返回: Result 对象
     */
    public static <T> Result<T> fail(String message) {
        return fail(500, message);
    }
}
