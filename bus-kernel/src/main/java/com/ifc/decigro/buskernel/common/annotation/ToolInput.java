package com.ifc.decigro.buskernel.common.annotation;

import java.lang.annotation.*;

/**
 * AI Tool Input Schema 自定义注解
 * 用于描述 Tool 入参的结构，帮助 Agent 生成准确的调用参数。
 */
@Target({ ElementType.FIELD, ElementType.PARAMETER })
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface ToolInput {

    /**
     * 参数名称 (param_name)
     * 对应 JSON Key 或 参数名，默认为字段名/参数名。
     */
    String param_name() default "";

    /**
     * 参数类型 (param_type)
     * 如: string, integer, number, boolean, array, object
     * 默认 string
     */
    String param_type() default "string";

    /**
     * 参数描述 (param_description)
     * 详细说明该参数的含义、约束条件或默认值。
     */
    String param_description() default "";

    /**
     * 是否必须 (param_required)
     * 默认为 true。
     */
    boolean param_required() default true;

    /**
     * 参数示例 (param_example)
     * 提供参数的典型值或格式示例。
     */
    String param_example() default "";
}
