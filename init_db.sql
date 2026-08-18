-- AI 导诊系统 - MySQL 数据库初始化脚本

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `患者病历库` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `患者病历库`;

-- ========== 患者信息表 ==========
CREATE TABLE IF NOT EXISTS `patients` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '患者ID',
  `patient_id` VARCHAR(50) NOT NULL UNIQUE COMMENT '患者编号',
  `surname` VARCHAR(50) NOT NULL COMMENT '姓氏',
  `gender` VARCHAR(10) NOT NULL COMMENT '性别',
  `age` INT NOT NULL COMMENT '年龄',
  `location` VARCHAR(100) DEFAULT '' COMMENT '地区',
  `contact` VARCHAR(20) DEFAULT '' COMMENT '联系方式',
  `email` VARCHAR(100) DEFAULT '' COMMENT '邮箱',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX idx_patient_id (`patient_id`),
  INDEX idx_surname (`surname`),
  INDEX idx_created_at (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='患者信息表';

-- ========== 问诊记录表 ==========
CREATE TABLE IF NOT EXISTS `consultations` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
  `thread_id` VARCHAR(100) NOT NULL UNIQUE COMMENT '线程ID',
  `patient_id` VARCHAR(50) NOT NULL COMMENT '患者编号',
  `patient_info_json` TEXT COMMENT '患者信息JSON',
  `symptoms_json` TEXT COMMENT '症状信息JSON',
  `diagnosis_text` TEXT COMMENT '诊断报告',
  `report_generated_at` TIMESTAMP NULL COMMENT '报告生成时间',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX idx_thread_id (`thread_id`),
  INDEX idx_patient_id (`patient_id`),
  INDEX idx_created_at (`created_at`),
  FOREIGN KEY (`patient_id`) REFERENCES `patients`(`patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问诊记录表';

-- ========== 医疗样例表 ==========
CREATE TABLE IF NOT EXISTS `medical_cases` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '样例ID',
  `patient_info_json` TEXT NOT NULL COMMENT '患者信息JSON',
  `symptoms_json` TEXT NOT NULL COMMENT '症状JSON',
  `diagnosis_text` TEXT NOT NULL COMMENT '诊断报告',
  `metadata_json` TEXT COMMENT '元数据JSON',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  INDEX idx_created_at (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='医疗样例表';

-- ========== 学习记录表 ==========
CREATE TABLE IF NOT EXISTS `learning_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
  `run_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '执行时间',
  `cases_processed` INT DEFAULT 0 COMMENT '处理样例数',
  `new_cases_added` INT DEFAULT 0 COMMENT '新增样例数',
  `embeddings_created` INT DEFAULT 0 COMMENT '生成的向量数',
  `status` VARCHAR(50) DEFAULT 'success' COMMENT '状态',
  `error_message` TEXT COMMENT '错误信息',
  INDEX idx_run_at (`run_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学习记录表';

-- ========== 健康建议表 ==========
CREATE TABLE IF NOT EXISTS `health_tips` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '建议ID',
  `category` VARCHAR(50) DEFAULT 'general' COMMENT '分类',
  `title` VARCHAR(200) NOT NULL COMMENT '标题',
  `content` TEXT NOT NULL COMMENT '内容',
  `source` VARCHAR(200) DEFAULT '' COMMENT '来源',
  `url` VARCHAR(500) DEFAULT '' COMMENT '原文链接',
  `summary` TEXT COMMENT '摘要',
  `digest` VARCHAR(64) DEFAULT '' COMMENT '内容摘要哈希',
  `published_at` TIMESTAMP NULL COMMENT '发布时间',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY `idx_digest` (`digest`),
  INDEX idx_category (`category`),
  INDEX idx_published_at (`published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康建议表';

-- ========== 爬虫调度表 ==========
CREATE TABLE IF NOT EXISTS `crawler_schedule` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '调度ID',
  `source` VARCHAR(50) NOT NULL COMMENT '数据源',
  `next_run_at` TIMESTAMP NOT NULL COMMENT '下次运行时间',
  `interval_hours` INT DEFAULT 24 COMMENT '运行间隔(小时)',
  `status` VARCHAR(20) DEFAULT 'pending' COMMENT '状态',
  `last_run_at` TIMESTAMP NULL COMMENT '上次运行时间',
  `last_status` VARCHAR(50) DEFAULT '' COMMENT '上次状态',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  UNIQUE KEY `idx_source` (`source`),
  INDEX idx_next_run (`next_run_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爬虫调度表';

-- ========== 插入默认调度配置 ==========
INSERT IGNORE INTO `crawler_schedule` (`source`, `next_run_at`, `interval_hours`) VALUES
('lancet', NOW() + INTERVAL 24 HOUR, 24),
('health_tips', NOW() + INTERVAL 24 HOUR, 24);

-- 创建示例管理员账户（密码需在应用中重新设置）
-- 注：实际部署时请通过管理端注册或直接修改 admin_users.json

GRANT ALL PRIVILEGES ON `患者病历库`.* TO 'medical'@'%';
FLUSH PRIVILEGES;