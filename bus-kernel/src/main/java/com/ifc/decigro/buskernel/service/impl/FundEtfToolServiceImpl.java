package com.ifc.decigro.buskernel.service.impl;

import com.alibaba.fastjson2.JSONObject;
import com.ifc.decigro.buskernel.service.GenericMongoService;
import org.bson.Document;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 场内基金特征值查询服务实现类
 * 功能: 处理 fund-etf-features 路径下的业务逻辑
 */
@Service
public class FundEtfToolServiceImpl implements GenericMongoService {

    @Autowired
    private MongoTemplate mongoTemplate;

    private static final String TOOL_PATH = "fund-etf-features";
    private static final String COLLECTION_NAME = "recommend_etf_features";

    @Override
    public boolean supports(String toolPath) {
        return TOOL_PATH.equalsIgnoreCase(toolPath);
    }

    @Override
    public List<JSONObject> executeQuery(Map<String, Object> params) {
        String fundCode = (String) params.get("fundCode");
        if (fundCode == null) {
            throw new IllegalArgumentException("缺少必需参数: fundCode");
        }

        // 构建 MongoDB 查询对象
        Query query = new Query(Criteria.where("FUND_CODE").is(fundCode));

        // 执行查询
        List<Document> documents = mongoTemplate.find(query, Document.class, COLLECTION_NAME);

        return documents.stream()
                .map(doc -> JSONObject.parseObject(doc.toJson()))
                .collect(Collectors.toList());
    }
}
