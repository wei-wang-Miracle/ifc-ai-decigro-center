package com.ifc.decigro.buskernel.config;

import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import org.springdoc.core.customizers.OperationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.StringUtils;

/**
 * OpenAPI 配置类
 * 用于集成 springdoc-openapi 自动化生成接口文档
 */
@Configuration
public class OpenApiConfig {

    /**
     * 自定义 OpenAPI 对象
     *
     * @return OpenAPI
     */
    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("DeciGro Center 接口文档")
                        .version("1.0.0")
                        .description("DeciGro Center 业务内核（bus-kernel）接口文档，提供系统管理、权限控制等核心功能。")
                        .termsOfService("https://github.com/wei-wang-Miracle/ifc-ai-decigro-center")
                        .license(new License().name("Apache 2.0").url("http://springdoc.org")));
    }

    /**
     * 自定义 OperationCustomizer，用于支持 @ToolCard 注解
     * 替换原生的 @Operation 逻辑，注入 AI Tool Card 相关的概念约束
     *
     * @return OperationCustomizer
     */
    @Bean
    public OperationCustomizer toolCardCustomizer() {
        return (operation, handlerMethod) -> {
            ToolCard toolCard = handlerMethod.getMethodAnnotation(ToolCard.class);
            if (toolCard != null) {
                // 1. 设置 Summary (工具摘要)
                if (StringUtils.hasText(toolCard.summary())) {
                    operation.setSummary(toolCard.summary());
                }

                // 2. 设置 Description (作为 tool_description)
                // 此处即实现了“不改变字段名称，但是进行概念升级约束”
                if (StringUtils.hasText(toolCard.description())) {
                    operation.setDescription(toolCard.description());
                }

                // 3. 设置 tool_name (对应 operationId)
                if (StringUtils.hasText(toolCard.tool_name())) {
                    operation.setOperationId(toolCard.tool_name());
                }

                // 4. 注入扩展元数据，方便后续 AI Engine 解析
                operation.addExtension("x-tool-card", true);
                operation.addExtension("x-audit-enabled", toolCard.audit());
                if (StringUtils.hasText(toolCard.tool_name())) {
                    operation.addExtension("x-tool-name", toolCard.tool_name());
                }
            }
            return operation;
        };
    }
}
