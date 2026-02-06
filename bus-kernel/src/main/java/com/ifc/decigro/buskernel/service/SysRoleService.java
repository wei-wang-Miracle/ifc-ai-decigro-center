package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.SysRole;
import java.util.List;

public interface SysRoleService {
    List<SysRole> list();
    void saveOrUpdate(SysRole role);
    void deleteById(Long id);
}
