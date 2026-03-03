package com.ifc.decigro.buskernel.config;

import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * StarRocks 数据源配置
 * 功能: 独立于主数据源，单独配置 StarRocks 连接池（兼容 MySQL 协议）。
 * 注意: 不将 DataSource 作为 Bean 暴露，避免干扰 MyBatis-Flex 对主库 DataSource 的自动装配。
 */
@Configuration
public class StarRocksDataSourceConfig {

    @Value("${starrocks.datasource.url}")
    private String url;

    @Value("${starrocks.datasource.username}")
    private String username;

    @Value("${starrocks.datasource.password}")
    private String password;

    @Value("${starrocks.datasource.min-idle:1}")
    private int minIdle;

    @Value("${starrocks.datasource.max-active:50}")
    private int maxActive;

    @Bean(name = "starRocksJdbcTemplate", destroyMethod = "")
    public JdbcTemplate starRocksJdbcTemplate() {
        HikariDataSource ds = new HikariDataSource();
        ds.setDriverClassName("com.mysql.cj.jdbc.Driver");
        ds.setJdbcUrl(url);
        ds.setUsername(username);
        ds.setPassword(password);
        ds.setMinimumIdle(minIdle);
        ds.setMaximumPoolSize(maxActive);
        ds.setConnectionTestQuery("select 1");
        ds.setPoolName("StarRocksPool");
        return new JdbcTemplate(ds);
    }
}
