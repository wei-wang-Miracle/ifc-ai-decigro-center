import { createRouter, createWebHistory } from "vue-router";
import { useUserStore } from "../stores/user";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("../views/login/index.vue"),
    },
    {
      path: "/",
      name: "home",
      component: () => import("../layout/index.vue"),
      redirect: "/system/user",
      children: [
        {
          path: "/system/user",
          name: "UserManagement",
          component: () => import("../views/system/user/index.vue"),
          meta: { title: "用户管理" },
        },
        {
          path: "/system/role",
          name: "RoleManagement",
          component: () => import("../views/system/role/index.vue"),
          meta: { title: "角色管理" },
        },
        {
          path: "/system/dept",
          name: "DeptManagement",
          component: () => import("../views/system/dept/index.vue"),
          meta: { title: "部门管理" },
        },
        {
          path: "/system/tenant",
          name: "TenantManagement",
          component: () => import("../views/system/tenant/index.vue"),
          meta: { title: "租户管理" },
        },
        {
          path: "/system/profile",
          name: "UserProfile",
          component: () => import("../views/system/profile/index.vue"),
          meta: { title: "个人信息" },
        },
        {
          path: "/system/password",
          name: "UserPassword",
          component: () => import("../views/system/profile/password.vue"),
          meta: { title: "修改密码" },
        },
        {
          path: "/tool/list",
          name: "ToolManagement",
          component: () => import("../views/tool/index.vue"),
          meta: { title: "工具管理" },
        },
        {
          path: "/agent/list",
          name: "AgentManagement",
          component: () => import("../views/agent/index.vue"),
          meta: { title: "智能体管理" },
        },
        {
          path: "/chat/index",
          name: "AIChat",
          component: () => import("../views/chat/index.vue"),
          meta: { title: "AI 智能对话" },
        },
        {
          path: "/audit/list",
          name: "AuditMonitoring",
          component: () => import("../views/audit/index.vue"),
          meta: { title: "审计监控" },
        },
      ],
    },
  ],
});

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore();
  if (to.name !== "login" && !userStore.token) {
    next({ name: "login" });
  } else {
    next();
  }
});

export default router;
