package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 基础实体类
 * 抽象公共字段：创建时间和更新时间
 */
@Getter
@Setter
public abstract class BaseEntity implements Serializable {

    /**
     * 创建时间
     * 当数据插入时，由数据库生成当前时间 (MyBatis-Flex 特性)
     */
    @Column(onInsertValue = "now()")
    private LocalDateTime createdTime;

    /**
     * 更新时间
     * 当数据插入或更新时，由数据库生成当前时间 (MyBatis-Flex 特性)
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private LocalDateTime updatedTime;
}
