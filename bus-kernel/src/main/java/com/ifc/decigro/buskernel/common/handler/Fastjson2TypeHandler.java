package com.ifc.decigro.buskernel.common.handler;

import com.alibaba.fastjson2.JSON;
import org.apache.ibatis.type.BaseTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.postgresql.util.PGobject;

import java.lang.reflect.Type;
import java.sql.CallableStatement;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

/**
 * 功能: 自定义 Fastjson2 类型处理器，专门针对 PostgreSQL 的 JSONB 类型。
 * 解决 MyBatis-Flex 默认处理器在 Postgres 下将 JSON 字符串传输为 varchar 导致的类型不匹配错误。
 * 
 * 参数: propertyType 属性类型
 */
public class Fastjson2TypeHandler extends BaseTypeHandler<Object> {

    private final Class<?> propertyType;

    /**
     * 功能: 构造函数，由 MyBatis 自动调用并传入属性类型。
     */
    public Fastjson2TypeHandler(Class<?> propertyType) {
        this.propertyType = propertyType;
    }

    @Override
    public void setNonNullParameter(PreparedStatement ps, int i, Object parameter, JdbcType jdbcType) throws SQLException {
        // 第一步：创建 PostgreSQL 的 PGobject 对象
        PGobject jsonObject = new PGobject();
        // 第二步：明确指定类型为 jsonb
        jsonObject.setType("jsonb");
        // 第三步：将对象序列化为 JSON 字符串
        jsonObject.setValue(JSON.toJSONString(parameter));
        // 第四步：使用 setObject 传递给 JDBC 驱动
        ps.setObject(i, jsonObject);
    }

    @Override
    public Object getNullableResult(ResultSet rs, String columnName) throws SQLException {
        return parse(rs.getString(columnName));
    }

    @Override
    public Object getNullableResult(ResultSet rs, int columnIndex) throws SQLException {
        return parse(rs.getString(columnIndex));
    }

    @Override
    public Object getNullableResult(CallableStatement cs, int columnIndex) throws SQLException {
        return parse(cs.getString(columnIndex));
    }

    /**
     * 功能: 将 JSON 字符串解析为目标 Java 对象。
     */
    private Object parse(String json) {
        if (json == null || json.isEmpty()) {
            return null;
        }
        return JSON.parseObject(json, (Type) propertyType);
    }
}
