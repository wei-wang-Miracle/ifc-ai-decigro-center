package com.ifc.decigro.buskernel.common.crypto;

import cn.hutool.crypto.asymmetric.KeyType;
import cn.hutool.crypto.asymmetric.RSA;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;

/**
 * RSA 加解密工具类
 * 用于处理前端加密传输的敏感信息
 */
@Component
public class RsaUtils {

    @Value("${crypto.rsa.private-key}")
    private String privateKey;

    @Value("${crypto.rsa.public-key}")
    private String publicKey;

    private RSA rsa;

    @PostConstruct
    public void init() {
        // 清理密钥字符串，移除 PEM 头尾和换行符
        String cleanPrivateKey = cleanKey(privateKey);
        String cleanPublicKey = cleanKey(publicKey);
        this.rsa = new RSA(cleanPrivateKey, cleanPublicKey);
    }

    private String cleanKey(String key) {
        if (key == null) return null;
        return key.replace("-----BEGIN PUBLIC KEY-----", "")
                  .replace("-----END PUBLIC KEY-----", "")
                  .replace("-----BEGIN PRIVATE KEY-----", "")
                  .replace("-----END PRIVATE KEY-----", "")
                  .replaceAll("\\s+", "");
    }

    /**
     * 解密
     * @param encryptedData 加密后的 Base64 字符串
     * @return 解密后的明文
     */
    public String decrypt(String encryptedData) {
        if (encryptedData == null || encryptedData.isBlank()) {
            return encryptedData;
        }
        try {
            return rsa.decryptStr(encryptedData, KeyType.PrivateKey);
        } catch (Exception e) {
            // 如果解密失败，返回原值（可能是明文，用于过渡或非加密场景）
            return encryptedData;
        }
    }

    /**
     * 加密 (通常由前端执行)
     */
    public String encrypt(String data) {
        return rsa.encryptBase64(data, KeyType.PublicKey);
    }
}
