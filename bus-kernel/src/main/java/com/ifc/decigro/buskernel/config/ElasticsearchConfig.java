package com.ifc.decigro.buskernel.config;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.json.jackson.JacksonJsonpMapper;
import co.elastic.clients.transport.ElasticsearchTransport;
import co.elastic.clients.transport.rest_client.RestClientTransport;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Elasticsearch 客户端配置
 * 功能: 创建 ElasticsearchClient Bean，供 Service 层注入使用
 */
@Configuration
public class ElasticsearchConfig {

    @Value("${elasticsearch.host:localhost}")
    private String host;

    @Value("${elasticsearch.port:9200}")
    private int port;

    /**
     * 创建低级别 REST 客户端
     */
    @Bean
    public RestClient restClient() {
        return RestClient.builder(
                new HttpHost(host, port, "http")).build();
    }

    /**
     * 创建 Elasticsearch Java 客户端
     * 使用 Jackson 作为 JSON 序列化器
     */
    @Bean
    public ElasticsearchClient elasticsearchClient(RestClient restClient) {
        ElasticsearchTransport transport = new RestClientTransport(
                restClient,
                new JacksonJsonpMapper());
        return new ElasticsearchClient(transport);
    }
}
