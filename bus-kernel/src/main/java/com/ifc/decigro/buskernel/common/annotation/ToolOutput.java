package com.ifc.decigro.buskernel.common.annotation;

import java.lang.annotation.*;

/**
 * AI Tool Output Schema 自定义注解
 * 用于描述 Tool 返回结果的结构，帮助 Agent 解析 JSON 输出。
 */
@Target({ ElementType.FIELD })
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface ToolOutput {

    /**
     * 参数名称 (param_name)
     * 对应 JSON Key，默认为字段名。
     */
    String param_name() default "";

    /**
     * 参数类型 (param_type)
     * 如: string, integer, array, object, boolean
     */
    String param_type() default "string";

    /**
     * 参数示例 (param_example)
     * 可选，提供典型值示例。
     */
    String param_example() default "";

    /**
     * 参数描述 (param_description)
     * 详细说明该字段的含义、取值范围或用途。
     */
    String param_description() default "";

    /**
     * 是否必须 (param_required)
     * 默认 true
     */
    boolean param_required() default true;
}
