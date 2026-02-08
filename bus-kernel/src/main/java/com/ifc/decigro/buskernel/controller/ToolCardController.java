package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.ToolCard;
import com.ifc.decigro.buskernel.service.ToolCardService;
import com.mybatisflex.core.paginate.Page;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * MAS 工具卡片管理控制器
 * 功能: 提供工具元数据的 CRUD 和生命周期管理 API
 */
@RestController
@RequestMapping("/tool")
@Tag(name = "工具管理", description = "MAS 工具注册中心 API")
public class ToolCardController {

    @Autowired
    private ToolCardService toolCardService;

    /**
     * 分页查询工具列表
     * 
     * 参数说明:
     * - keyword: 关键字（可选），模糊搜索工具名称或描述
     * - tag: 标签（可选），筛选包含该标签的工具
     * - page: 页码，默认1
     * - size: 每页条数，默认20
     */
    @GetMapping("/page")
    @Operation(summary = "分页查询工具列表", description = "支持按名称、描述关键字和标签筛选")
    public Result<Page<ToolCard>> page(
            @Parameter(description = "关键字，模糊匹配名称或描述") @RequestParam(required = false) String keyword,
            @Parameter(description = "标签筛选") @RequestParam(required = false) String tag,
            @Parameter(description = "页码") @RequestParam(defaultValue = "1") int page,
            @Parameter(description = "每页条数") @RequestParam(defaultValue = "10") int size) {
        return Result.success(toolCardService.page(keyword, tag, page, size));
    }

    /**
     * 根据 ID 获取工具详情
     */
    @GetMapping("/detail/{id}")
    @Operation(summary = "获取工具详情", description = "根据 ID 查询单个工具的完整信息")
    public Result<ToolCard> getById(
            @Parameter(description = "工具ID") @PathVariable Long id) {
        return Result.success(toolCardService.getById(id));
    }

    /**
     * 新增或更新工具
     * - 当 id 为空时执行新增
     * - 当 id 有值时执行更新
     */
    @PostMapping("/save")
    @Operation(summary = "新增/更新工具", description = "ID 为空时新增，有值时更新。会校验 tool_name 唯一性")
    public Result<Void> save(@RequestBody ToolCard toolCard) {
        toolCardService.saveOrUpdate(toolCard);
        return Result.success();
    }

    /**
     * 删除工具
     */
    @DeleteMapping("/remove/{id}")
    @Operation(summary = "删除工具", description = "根据 ID 删除工具")
    public Result<Void> delete(
            @Parameter(description = "工具ID") @PathVariable Long id) {
        toolCardService.deleteById(id);
        return Result.success();
    }

    /**
     * 工具上线
     * 将工具状态设置为 is_online = true
     */
    @PutMapping("/online/{id}")
    @Operation(summary = "工具上线", description = "将工具标记为上线状态，对 Agent 可见")
    public Result<Void> online(
            @Parameter(description = "工具ID") @PathVariable Long id) {
        toolCardService.updateOnlineStatus(id, true);
        return Result.success();
    }

    /**
     * 工具下线
     * 将工具状态设置为 is_online = false
     */
    @PutMapping("/offline/{id}")
    @Operation(summary = "工具下线", description = "将工具标记为下线状态，Agent 不可见")
    public Result<Void> offline(
            @Parameter(description = "工具ID") @PathVariable Long id) {
        toolCardService.updateOnlineStatus(id, false);
        return Result.success();
    }

    /**
     * 检查工具名称是否可用
     * 用于前端实时校验
     */
    @GetMapping("/check-name")
    @Operation(summary = "检查工具名称可用性", description = "检查 tool_name 是否已被使用")
    public Result<Boolean> checkName(
            @Parameter(description = "工具名称") @RequestParam String toolName,
            @Parameter(description = "排除的ID（编辑时传入当前工具ID）") @RequestParam(required = false) Long excludeId) {
        boolean exists = toolCardService.existsByToolName(toolName, excludeId);
        return Result.success(!exists); // 返回 true 表示可用
    }
}
