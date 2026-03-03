package com.ifc.decigro.buskernel.service;

import com.alibaba.fastjson2.JSONObject;
import java.util.List;
import java.util.Map;

/**
 * 通用 MongoDB 业务服务接口
 * 功能: 定义业务查询逻辑，支持由 Controller 动态分发
 */
public interface GenericMongoService {

    /**
     * 判断当前 Service 是否支持处理该工具路径
     * 
     * @param toolPath 工具路径标识
     * @return true=支持, false=不支持
     */
    boolean supports(String toolPath);

    /**
     * 执行具体的 MongoDB 业务查询
     * 
     * @param params 请求参数 Map
     * @return 查询结果列表
     */
    List<JSONObject> executeQuery(Map<String, Object> params);
}
