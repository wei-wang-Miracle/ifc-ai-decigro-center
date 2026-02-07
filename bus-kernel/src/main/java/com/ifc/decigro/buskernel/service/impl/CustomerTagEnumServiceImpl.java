package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.CustomerTagEnum;
import com.ifc.decigro.buskernel.mapper.CustomerTagEnumMapper;
import com.ifc.decigro.buskernel.service.CustomerTagEnumService;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 标签枚举值服务实现类
 * 功能: 实现枚举值的增删改查和批量保存
 */
@Service
public class CustomerTagEnumServiceImpl implements CustomerTagEnumService {

    @Autowired
    private CustomerTagEnumMapper enumMapper;

    @Override
    public List<CustomerTagEnum> listByTagField(String tagField) {
        return enumMapper.selectListByQuery(
                QueryWrapper.create()
                        .where("tag_field = ?", tagField));
    }

    @Override
    public void saveOrUpdate(CustomerTagEnum enumItem) {
        if (enumItem.getId() == null) {
            enumMapper.insert(enumItem);
        } else {
            enumMapper.update(enumItem);
        }
    }

    @Override
    public void deleteById(Long id) {
        enumMapper.deleteById(id);
    }

    /**
     * 批量保存枚举值
     * 采用"先删后插"策略，保证数据一致性
     */
    @Override
    @Transactional
    public void batchSave(String tagField, List<CustomerTagEnum> items) {
        // 第一步：删除该标签的所有现有枚举值
        deleteByTagField(tagField);

        // 第二步：批量插入新值
        if (items != null && !items.isEmpty()) {
            for (CustomerTagEnum item : items) {
                item.setTagField(tagField);
                item.setId(null); // 确保使用新ID
            }
            enumMapper.insertBatch(items);
        }
    }

    @Override
    public void deleteByTagField(String tagField) {
        enumMapper.deleteByQuery(
                QueryWrapper.create()
                        .where("tag_field = ?", tagField));
    }
}
