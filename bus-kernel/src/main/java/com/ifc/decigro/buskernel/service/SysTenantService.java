package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.SysTenant;
import java.util.List;

public interface SysTenantService {
    List<SysTenant> list();
    void saveOrUpdate(SysTenant tenant);
    void deleteById(String id);
}
