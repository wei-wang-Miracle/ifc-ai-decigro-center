package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.SysDept;
import com.ifc.decigro.buskernel.mapper.SysDeptMapper;
import com.ifc.decigro.buskernel.service.SysDeptService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

@Service
public class SysDeptServiceImpl implements SysDeptService {

    @Autowired
    private SysDeptMapper deptMapper;

    @Override
    public List<SysDept> list() {
        return deptMapper.selectAll();
    }

    @Override
    public void saveOrUpdate(SysDept dept) {
        if (dept.getDeptId() == null) {
            deptMapper.insert(dept);
        } else {
            deptMapper.update(dept);
        }
    }

    @Override
    public void deleteById(Long id) {
        deptMapper.deleteById(id);
    }

    @Override
    public List<SysDept> tree() {
        List<SysDept> all = deptMapper.selectAll();
        return buildTree(all, 0L);
    }

    private List<SysDept> buildTree(List<SysDept> all, Long parentId) {
        return all.stream()
                .filter(dept -> Objects.equals(dept.getParentId(), parentId))
                .map(dept -> {
                    dept.setChildren(buildTree(all, dept.getDeptId()));
                    return dept;
                })
                .collect(Collectors.toList());
    }
}
