package com.ifc.decigro.buskernel.config;

import com.ifc.decigro.buskernel.common.context.UserContext;
import com.mybatisflex.core.tenant.TenantFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MyBatis-Flex 配置
 * 配置多租户工厂
 */
@Configuration
public class MyBatisFlexConfig {

    @Bean
    public TenantFactory tenantFactory() {
        return new TenantFactory() {
            @Override
            public Object[] getTenantIds() {
                // Return the current tenant ID from the context
                String tenantCode = UserContext.getTenantCode();
                if (tenantCode != null) {
                    return new Object[] { tenantCode };
                }
                return null;
            }
        };
    }
}
