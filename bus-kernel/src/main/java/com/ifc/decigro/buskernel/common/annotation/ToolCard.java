package com.ifc.decigro.buskernel.common.annotation;

import java.lang.annotation.*;

/**
 * AI Tool Card 自定义注解
 * 符合 README 中的 "AI-friendly Tool Card" 设计思想，作为 AI 的“自述文件”。
 * 本注解通过概念升级，替代原有的 @Operation 注解，专门用于描述 AIGC 场景下的工具能力。
 */
@Target({ ElementType.METHOD })
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface ToolCard {

    /**
     * 工具唯一标识 (tool_name)
     * 要求: 语义清晰，建议用 snake_case，如 get_weather_data。
     * 如果为空，文档将尝试使用方法名。
     *
     * @return 工具名称
     */
    String tool_name() default "";

    /**
     * 工具摘要 (summary)
     * 简明扼要说明工具功能。对应 原 @Operation.summary
     *
     * @return 工具摘要
     */
    String summary() default "";

    /**
     * 工具详细描述 (tool_description)
     * 对应 README 要求的 AI 友好写法。对应 原 @Operation.description
     * 约束要求:
     * 1. 必须包含 "做什么" (Action)
     * 2. 必须包含 "什么时候用" (Trigger)
     * 3. 必须包含 "局持性" (Constraint)
     *
     * @return 工具描述
     */
    String description() default "";

    /**
     * 是否启用审计记录
     *
     * @return 是否审计
     */
    boolean audit() default true;
}
