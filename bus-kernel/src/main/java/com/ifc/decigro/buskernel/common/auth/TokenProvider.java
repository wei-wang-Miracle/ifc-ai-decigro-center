package com.ifc.decigro.buskernel.common.auth;

import cn.hutool.core.date.DateUtil;
import cn.hutool.crypto.digest.HMac;
import cn.hutool.crypto.digest.HmacAlgorithm;
import org.springframework.stereotype.Component;

/**
 * Token 生成器
 * 实现签名式长效令牌机制
 */
@Component
public class TokenProvider {

    // TODO: Should be loaded from environment/config
    private static final String SYSTEM_SECRET = "sys_secret_key_123456";
    private static final String PREFIX = "skv1";
    private static final String SEPARATOR = "_";

    /**
     * 生成 Token
     * 格式: Prefix_TenantCode_DeptId_UserName_Timestamp_Signature
     */
    public String createToken(String tenantCode, String deptId, String username) {
        long timestamp = DateUtil.currentSeconds();
        String rawData = String.join(SEPARATOR, PREFIX, tenantCode, deptId, username, String.valueOf(timestamp));

        HMac hmac = new HMac(HmacAlgorithm.HmacSHA256, SYSTEM_SECRET.getBytes());
        String signature = hmac.digestHex(rawData);

        return rawData + SEPARATOR + signature;
    }

    /**
     * 验证并解析 Token
     * 
     * @return 解析出的信息数组 [Prefix, TenantCode, DeptId, UserName, Timestamp]
     * @throws IllegalArgumentException 如果 Token 无效
     */
    public String[] validateAndParse(String token) {
        if (token == null || token.isBlank()) {
            throw new IllegalArgumentException("Token is empty");
        }

        int lastSeparatorIndex = token.lastIndexOf(SEPARATOR);
        if (lastSeparatorIndex == -1) {
            throw new IllegalArgumentException("Invalid Token format");
        }

        String rawData = token.substring(0, lastSeparatorIndex);
        String signature = token.substring(lastSeparatorIndex + 1);

        HMac hmac = new HMac(HmacAlgorithm.HmacSHA256, SYSTEM_SECRET.getBytes());
        String calculatedSignature = hmac.digestHex(rawData);

        if (!calculatedSignature.equals(signature)) {
            throw new IllegalArgumentException("Invalid Token signature");
        }

        return rawData.split(SEPARATOR);
    }
}
