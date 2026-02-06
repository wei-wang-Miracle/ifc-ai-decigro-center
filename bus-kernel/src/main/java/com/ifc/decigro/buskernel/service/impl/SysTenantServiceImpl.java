package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.SysTenant;
import com.ifc.decigro.buskernel.mapper.SysTenantMapper;
import com.ifc.decigro.buskernel.service.SysTenantService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class SysTenantServiceImpl implements SysTenantService {

    @Autowired
    private SysTenantMapper tenantMapper;

    @Override
    public List<SysTenant> list() {
        return tenantMapper.selectAll();
    }

    @Override
    public void saveOrUpdate(SysTenant tenant) {
        if (tenantMapper.selectOneById(tenant.getTenantCode()) != null) {
            tenantMapper.update(tenant);
        } else {
            tenantMapper.insert(tenant);
        }
    }

    @Override
    public void deleteById(String id) {
        tenantMapper.deleteById(id);
    }
}
