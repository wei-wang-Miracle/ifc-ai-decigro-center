package com.ifc.decigro.buskernel.config;

import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

/**
 * StarRocks 数据源配置
 * 功能: 独立于主数据源，单独配置 StarRocks 连接池（兼容 MySQL 协议）。
 * 注意: 不将 StarRocks DataSource 作为 Bean 暴露，避免干扰 MyBatis-Flex 对主库 DataSource 的自动装配。
 *       同时显式注册主库 JdbcTemplate（@Primary），防止 Spring Boot 自动配置因本类中已注册
 *       JdbcTemplate Bean 而跳过主库的 JdbcTemplate 自动装配。
 */
@Configuration
public class StarRocksDataSourceConfig {

    /**
     * 主库 JdbcTemplate（PostgreSQL），标记为 @Primary。
     * 解决：当容器中存在多个 JdbcTemplate Bean 时，@Autowired 按类型注入会产生歧义，
     * @Primary 保证 AiChatServiceImpl 等未指定 @Qualifier 的注入点默认使用主库。
     */
    @Primary
    @Bean(name = "jdbcTemplate")
    public JdbcTemplate jdbcTemplate(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }

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
