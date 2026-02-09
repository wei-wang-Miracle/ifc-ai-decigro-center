package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.SysRole;
import com.ifc.decigro.buskernel.mapper.SysRoleMapper;
import com.ifc.decigro.buskernel.service.SysRoleService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class SysRoleServiceImpl implements SysRoleService {

    @Autowired
    private SysRoleMapper roleMapper;

    @Override
    public List<SysRole> list() {
        return roleMapper.selectAll();
    }

    @Override
    public SysRole getById(Long id) {
        return roleMapper.selectOneById(id);
    }

    @Override
    public void saveOrUpdate(SysRole role) {
        if (role.getRoleId() == null) {
            roleMapper.insert(role);
        } else {
            roleMapper.update(role);
        }
    }

    @Override
    public void deleteById(Long id) {
        roleMapper.deleteById(id);
    }
}
