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
     * 工具别名 (alias)
     * 用于前端展示或语义标注
     *
     * @return 工具别名
     */
    String alias() default "";

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
     * 工具标签 (tags)
     * 用于分类检索，如 "user", "admin"
     */
    String[] tags() default {};

    /**
     * 工具版本号 (version)
     * 默认 "1.0.0"
     */
    String version() default "1.0.0";

    /**
     * 权限级别 (privileges)
     * 枚举值：public（公开可用）、protected（需授权）
     * 默认 protected
     */
    String privileges() default "protected";

    /**
     * 输入示例 (input_examples)
     * 提供 Few-Shot Prompt 的输入示例
     */
    String input_examples() default "";

    /**
     * 输出示例 (output_examples)
     * 提供 Few-Shot Prompt 的输出示例
     */
    String output_examples() default "";

    /**
     * 管理人 (manager)
     * 默认 system
     */
    String manager() default "system";

    /**
     * HTTP 请求方法 (http_method)
     * 仅当 toolProtocol = "http" 时生效
     * 枚举值：GET、POST（默认）、PUT、DELETE
     */
    String http_method() default "POST";

    /**
     * 自定义请求头 (headers)
     * 格式为 "Key:Value" 数组，例如 {"Content-Type:application/json", "X-Custom:value"}
     * 这些 Header 会附加在请求中（X-Auth-Token 由系统自动注入，无需在此配置）
     */
    String[] headers() default {};

    /**
     * 是否启用审计记录
     *
     * @return 是否审计
     */
    boolean audit() default true;
}
