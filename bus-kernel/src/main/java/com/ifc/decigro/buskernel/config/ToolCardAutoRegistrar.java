package com.ifc.decigro.buskernel.config;

import cn.hutool.core.util.StrUtil;
import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import com.ifc.decigro.buskernel.common.annotation.ToolOutput;
import com.ifc.decigro.buskernel.entity.ToolCard;
import com.ifc.decigro.buskernel.service.ToolCardService;
import lombok.extern.slf4j.Slf4j;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.stereotype.Component;
import org.springframework.lang.NonNull;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.mvc.method.RequestMappingInfo;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

import java.lang.reflect.Field;
import java.lang.reflect.Parameter;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.*;
import org.springframework.web.util.pattern.PathPattern;

/**
 * 自动注册 ToolCard
 * 监听 Spring 启动事件，扫描带有 @ToolCard 注解的接口，自动注册为系统工具。
 */
@Slf4j
@Component
public class ToolCardAutoRegistrar implements ApplicationListener<ApplicationReadyEvent> {

    @Autowired
    private RequestMappingHandlerMapping requestMappingHandlerMapping;

    @Autowired
    private ToolCardService toolCardService;

    @Override
    public void onApplicationEvent(@NonNull ApplicationReadyEvent event) {
        log.info("开始扫描并自动注册 Tool Cards...");
        Map<RequestMappingInfo, HandlerMethod> handlerMethods = requestMappingHandlerMapping.getHandlerMethods();
        int count = 0;

        for (Map.Entry<RequestMappingInfo, HandlerMethod> entry : handlerMethods.entrySet()) {
            RequestMappingInfo mappingInfo = entry.getKey();
            HandlerMethod method = entry.getValue();

            // 1. 检查方法上是否有 @ToolCard 注解
            com.ifc.decigro.buskernel.common.annotation.ToolCard annotation = method
                    .getMethodAnnotation(com.ifc.decigro.buskernel.common.annotation.ToolCard.class);

            if (annotation != null) {
                try {
                    processToolCard(mappingInfo, method, annotation);
                    count++;
                } catch (Exception e) {
                    log.error("自动注册工具失败: {}", method.getMethod().getName(), e);
                }
            }
        }
        log.info("Tool Cards 自动注册完成，共处理 {} 个工具。", count);
    }

    private void processToolCard(RequestMappingInfo mappingInfo, HandlerMethod method,
            com.ifc.decigro.buskernel.common.annotation.ToolCard annotation) {
        // 2. 确定工具名称
        String toolName = annotation.tool_name();
        if (toolName == null || toolName.isEmpty()) {
            // 默认使用方法名转 snake_case
            toolName = StrUtil.toUnderlineCase(method.getMethod().getName());
        }

        // 3. 构建核心技术参数 (Hard Contract)
        // 提取协议与路径
        String toolProtocol = "http";
        String urlPath = null;
        // 优先尝试 PathPatternsCondition (Spring Boot 2.6+)
        if (mappingInfo.getPathPatternsCondition() != null) {
            Set<PathPattern> patterns = mappingInfo.getPathPatternsCondition()
                    .getPatterns();
            if (!patterns.isEmpty()) {
                urlPath = patterns.iterator().next().getPatternString();
            }
        }

        // 降级尝试 PatternsCondition (Legacy)
        if (urlPath == null && mappingInfo.getPatternsCondition() != null) {
            Set<String> patterns = mappingInfo.getPatternsCondition().getPatterns();
            if (!patterns.isEmpty()) {
                urlPath = patterns.iterator().next();
            }
        }

        // 解析入参 (ToolInput)
        List<Map<String, Object>> inputSchema = parseInputSchema(method);

        // 解析出参 (ToolOutput)
        List<Map<String, Object>> outputSchema = parseOutputSchema(method);

        // 4. 检查是否已存在
        ToolCard existTool = toolCardService.getById(toolName);

        if (existTool != null) {
            // === 已存在：仅更新硬契约 (Technical Spec) ===
            log.info("工具 {} 已存在，正在同步技术契约(Schema/Path/Alias)...", toolName);

            existTool.setToolProtocol(toolProtocol);
            existTool.setUrlPath(urlPath);
            existTool.setToolParameters(inputSchema);
            existTool.setOutputSchema(outputSchema);
            // 同步别名（如果注解中有定义）
            if (StrUtil.isNotBlank(annotation.alias())) {
                existTool.setToolAlias(annotation.alias());
            }

            // 注意：Description, Tags, Examples, Manager, Privileges 等软描述字段保持 DB 原值，不覆盖
            toolCardService.saveOrUpdate(existTool);
        } else {
            // === 新增：保存所有字段 ===
            log.info("发现新工具 {}，正在注册...", toolName);

            ToolCard newTool = new ToolCard();
            newTool.setToolName(toolName);
            newTool.setToolAlias(annotation.alias());

            // 硬契约
            newTool.setToolProtocol(toolProtocol);
            newTool.setUrlPath(urlPath);
            newTool.setToolParameters(inputSchema);
            newTool.setOutputSchema(outputSchema);

            // 软描述 (仅新增时写入)
            newTool.setToolDescription(annotation.description());
            newTool.setToolTags(Arrays.asList(annotation.tags()));
            newTool.setToolVersion(annotation.version());
            newTool.setToolPrivileges(annotation.privileges());
            newTool.setManagerBy(annotation.manager());
            newTool.setInputExamples(annotation.input_examples());
            newTool.setOutputExamples(annotation.output_examples());
            newTool.setIsOnline(true); // 默认上线

            toolCardService.saveOrUpdate(newTool);
        }
    }

    /**
     * 解析入参 Schema
     */
    private List<Map<String, Object>> parseInputSchema(HandlerMethod method) {
        List<Map<String, Object>> schemaList = new ArrayList<>();
        Parameter[] parameters = method.getMethod().getParameters();

        for (Parameter param : parameters) {
            // 情况A: 参数本身被 @ToolInput 标记 (通常是简单类型 @RequestParam)
            ToolInput directAnnotation = param.getAnnotation(ToolInput.class);
            if (directAnnotation != null) {
                schemaList.add(buildParamMap(directAnnotation, param.getName(), param.getType()));
                continue;
            }

            // 情况B: 参数是复杂对象 (通常是 @RequestBody DTO)
            // 扫描该对象类中的 @ToolInput 字段
            Class<?> paramType = param.getType();
            if (!isSimpleType(paramType)) {
                // 递归扫描字段
                List<Map<String, Object>> fieldSchemas = scanFieldsForInput(paramType);
                schemaList.addAll(fieldSchemas);
            }
        }
        return schemaList;
    }

    private List<Map<String, Object>> scanFieldsForInput(Class<?> clazz) {
        List<Map<String, Object>> list = new ArrayList<>();
        // 简单处理: 扫描当前类及父类的所有字段
        Field[] fields = getAllFields(clazz);
        for (Field field : fields) {
            ToolInput inputAn = field.getAnnotation(ToolInput.class);
            if (inputAn != null) {
                list.add(buildParamMap(inputAn, field.getName(), field.getType()));
            }
        }
        return list;
    }

    /**
     * 解析出参 Schema
     */
    private List<Map<String, Object>> parseOutputSchema(HandlerMethod method) {
        List<Map<String, Object>> schemaList = new ArrayList<>();
        Type returnType = method.getMethod().getGenericReturnType();

        // 递归提取真实的实体类型，例如 Result<List<User>> -> User.class
        Class<?> actualClass = extractActualType(returnType);

        if (actualClass != null && !isSimpleType(actualClass)) {
            Field[] fields = getAllFields(actualClass);
            for (Field field : fields) {
                ToolOutput outputAn = field.getAnnotation(ToolOutput.class);
                if (outputAn != null) {
                    schemaList.add(buildOutputMap(outputAn, field.getName(), field.getType()));
                }
            }
        }
        return schemaList;
    }

    /**
     * 递归提取泛型中的核心实体类型
     * 支持 Result<T>, List<T>, Set<T>, Page<T> 等
     */
    private Class<?> extractActualType(Type type) {
        if (type instanceof Class) {
            return (Class<?>) type;
        } else if (type instanceof ParameterizedType) {
            ParameterizedType pt = (ParameterizedType) type;
            Type[] typeArgs = pt.getActualTypeArguments();
            if (typeArgs.length > 0) {
                // 取第一个泛型参数，继续递归
                // 例如 Result<List<User>> -> List<User> -> User
                return extractActualType(typeArgs[0]);
            }
        }
        return null;
    }

    // --- 辅助方法 ---

    private Map<String, Object> buildParamMap(ToolInput annotation, String defaultName, Class<?> type) {
        Map<String, Object> map = new HashMap<>();
        String name = annotation.param_name().isEmpty() ? defaultName : annotation.param_name();
        map.put("param_name", name);
        map.put("param_type", annotation.param_type().isEmpty() ? determineType(type) : annotation.param_type());
        map.put("param_description", annotation.param_description());
        map.put("param_required", annotation.param_required());
        map.put("param_example", annotation.param_example());
        return map;
    }

    private Map<String, Object> buildOutputMap(ToolOutput annotation, String defaultName, Class<?> type) {
        Map<String, Object> map = new HashMap<>();
        String name = annotation.param_name().isEmpty() ? defaultName : annotation.param_name();
        map.put("param_name", name);
        map.put("param_type", annotation.param_type().isEmpty() ? determineType(type) : annotation.param_type());
        map.put("param_description", annotation.param_description());
        map.put("param_required", annotation.param_required());
        map.put("param_example", annotation.param_example());
        return map;
    }

    private String determineType(Class<?> type) {
        if (Number.class.isAssignableFrom(type) || type == int.class || type == long.class || type == double.class) {
            return "number";
        } else if (Boolean.class.isAssignableFrom(type) || type == boolean.class) {
            return "boolean";
        } else if (List.class.isAssignableFrom(type) || type.isArray()) {
            return "array";
        } else if (Map.class.isAssignableFrom(type)) {
            return "object";
        }
        return "string";
    }

    private boolean isSimpleType(Class<?> type) {
        return type.isPrimitive() || type.equals(String.class) || Number.class.isAssignableFrom(type)
                || Boolean.class.isAssignableFrom(type) || Date.class.isAssignableFrom(type)
                || type.equals(Long.class) || type.equals(Integer.class);
    }

    private Field[] getAllFields(Class<?> clazz) {
        List<Field> fields = new ArrayList<>();
        while (clazz != null && clazz != Object.class) {
            Collections.addAll(fields, clazz.getDeclaredFields());
            clazz = clazz.getSuperclass();
        }
        return fields.toArray(new Field[0]);
    }
}
