-- HealthPro Sales Force Management System - 12-Table Relational Schema
-- Compatible with MySQL 8.0+

CREATE DATABASE IF NOT EXISTS `salesforce`;
USE `salesforce`;

-- Table: employee_details
DROP TABLE IF EXISTS `employee_details`;
CREATE TABLE `employee_details` (
  `emp_id` char(7) NOT NULL,
  `emp_name` varchar(150) NOT NULL,
  `dob` date NOT NULL,
  `designation` varchar(30) DEFAULT NULL,
  `emp_email` varchar(50) NOT NULL,
  `emp_phone` char(10) NOT NULL,
  `password` varchar(64) DEFAULT NULL,
  `salt` varchar(32) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `locked_out` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: sku_details
DROP TABLE IF EXISTS `sku_details`;
CREATE TABLE `sku_details` (
  `sku` char(5) NOT NULL,
  `sku_name` varchar(50) NOT NULL,
  `netwt` decimal(4,3) NOT NULL,
  `wholesale_price` decimal(5,2) NOT NULL DEFAULT '0.00',
  `active_sku` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`sku`),
  UNIQUE KEY `sku_name` (`sku_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: area
DROP TABLE IF EXISTS `area`;
CREATE TABLE `area` (
  `areacode` char(5) NOT NULL,
  `areaname` varchar(20) DEFAULT NULL,
  `emp_id` char(7) DEFAULT NULL,
  `population` int DEFAULT NULL,
  PRIMARY KEY (`areacode`),
  KEY `emp_id` (`emp_id`),
  CONSTRAINT `area_ibfk_1` FOREIGN KEY (`emp_id`) REFERENCES `employee_details` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: outlet_mapping
DROP TABLE IF EXISTS `outlet_mapping`;
CREATE TABLE `outlet_mapping` (
  `outletno` char(10) NOT NULL,
  `outletname` varchar(30) DEFAULT NULL,
  `outlet_address` varchar(150) NOT NULL,
  `areacode` char(5) NOT NULL,
  `billing_status_recent` enum('P','U','NV') NOT NULL DEFAULT 'NV',
  `active_outlet` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`outletno`),
  KEY `areacode` (`areacode`),
  CONSTRAINT `outlet_mapping_ibfk_1` FOREIGN KEY (`areacode`) REFERENCES `area` (`areacode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: crm
DROP TABLE IF EXISTS `crm`;
CREATE TABLE `crm` (
  `outletno` char(10) NOT NULL,
  `owner_name` varchar(150) DEFAULT NULL,
  `phone` char(10) DEFAULT NULL,
  `email` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`outletno`),
  CONSTRAINT `crm_ibfk_1` FOREIGN KEY (`outletno`) REFERENCES `outlet_mapping` (`outletno`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: daywise_attendance
DROP TABLE IF EXISTS `daywise_attendance`;
CREATE TABLE `daywise_attendance` (
  `emp_id` char(7) NOT NULL,
  `entry_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `exit_time` timestamp NULL DEFAULT NULL,
  `in_out` enum('IN','OUT','AB') NOT NULL DEFAULT 'AB',
  PRIMARY KEY (`emp_id`),
  CONSTRAINT `daywise_attendance_ibfk_1` FOREIGN KEY (`emp_id`) REFERENCES `employee_details` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: monthly_attendance
DROP TABLE IF EXISTS `monthly_attendance`;
CREATE TABLE `monthly_attendance` (
  `emp_id` char(7) NOT NULL,
  `month` int NOT NULL,
  `year` int NOT NULL,
  `days_present` int NOT NULL DEFAULT '0',
  `totaldays` int NOT NULL,
  PRIMARY KEY (`emp_id`,`month`,`year`),
  CONSTRAINT `monthly_attendance_ibfk_1` FOREIGN KEY (`emp_id`) REFERENCES `employee_details` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: targets
DROP TABLE IF EXISTS `targets`;
CREATE TABLE `targets` (
  `emp_id` char(7) NOT NULL,
  `tls` int NOT NULL DEFAULT '0',
  `sales` decimal(11,2) NOT NULL DEFAULT '0.00',
  `target_ls` int NOT NULL DEFAULT '0',
  `target_sales` decimal(11,2) NOT NULL DEFAULT '0.00',
  `ls_diff` int GENERATED ALWAYS AS ((`tls` - `target_ls`)) STORED,
  `sales_diff` decimal(11,2) GENERATED ALWAYS AS ((`sales` - `target_sales`)) STORED,
  PRIMARY KEY (`emp_id`),
  CONSTRAINT `targets_ibfk_1` FOREIGN KEY (`emp_id`) REFERENCES `employee_details` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: incentive_eligibility
DROP TABLE IF EXISTS `incentive_eligibility`;
CREATE TABLE `incentive_eligibility` (
  `emp_id` char(7) NOT NULL,
  `month` int NOT NULL,
  `year` int NOT NULL,
  `salescore` int NOT NULL DEFAULT '0',
  `incentive_eligible` decimal(11,2) NOT NULL DEFAULT '0.00',
  `admin_approval` enum('N','Y') DEFAULT NULL,
  PRIMARY KEY (`emp_id`,`month`,`year`),
  CONSTRAINT `incentive_eligibility_ibfk_1` FOREIGN KEY (`emp_id`) REFERENCES `employee_details` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: outlet_wise_stock
DROP TABLE IF EXISTS `outlet_wise_stock`;
CREATE TABLE `outlet_wise_stock` (
  `outletno` char(10) NOT NULL,
  `sku` char(5) NOT NULL,
  `stock` int NOT NULL DEFAULT '0',
  `max_capacity` int NOT NULL DEFAULT '0',
  `emptystock` int GENERATED ALWAYS AS ((`max_capacity` - `stock`)) STORED,
  PRIMARY KEY (`outletno`,`sku`),
  KEY `sku` (`sku`),
  CONSTRAINT `outlet_wise_stock_ibfk_1` FOREIGN KEY (`outletno`) REFERENCES `outlet_mapping` (`outletno`),
  CONSTRAINT `outlet_wise_stock_ibfk_2` FOREIGN KEY (`sku`) REFERENCES `sku_details` (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: order_data
DROP TABLE IF EXISTS `order_data`;
CREATE TABLE `order_data` (
  `orderno` int NOT NULL,
  `sku` char(5) NOT NULL,
  `outletno` char(10) NOT NULL,
  `emp_id` char(7) NOT NULL,
  `emptystock_on_order` int NOT NULL DEFAULT '0',
  `units` int NOT NULL DEFAULT '0',
  `amount` decimal(11,2) NOT NULL DEFAULT '0.00',
  `date_of_order` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `order_status` enum('PLACED','DISPATCHED','DELIVERED','CANCELLED') NOT NULL DEFAULT 'PLACED',
  `status_updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`orderno`,`sku`),
  KEY `sku` (`sku`),
  KEY `outletno` (`outletno`),
  KEY `emp_id` (`emp_id`),
  CONSTRAINT `order_data_ibfk_1` FOREIGN KEY (`sku`) REFERENCES `sku_details` (`sku`),
  CONSTRAINT `order_data_ibfk_2` FOREIGN KEY (`outletno`) REFERENCES `outlet_mapping` (`outletno`),
  CONSTRAINT `order_data_ibfk_3` FOREIGN KEY (`emp_id`) REFERENCES `employee_details` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table: erp
DROP TABLE IF EXISTS `erp`;
CREATE TABLE `erp` (
  `end_of_day` date NOT NULL,
  `sku` char(5) NOT NULL,
  `units_produced` int NOT NULL DEFAULT '0',
  `units_ordered` int NOT NULL DEFAULT '0',
  `units_inventory` int NOT NULL DEFAULT '0',
  `production_diff` int GENERATED ALWAYS AS ((`units_produced` - `units_ordered`)) STORED,
  `total_sales` decimal(11,2) NOT NULL DEFAULT '0.00',
  `target_sales` decimal(11,2) NOT NULL DEFAULT '0.00',
  `target_diff` decimal(11,2) GENERATED ALWAYS AS ((`total_sales` - `target_sales`)) STORED,
  PRIMARY KEY (`end_of_day`,`sku`),
  KEY `sku` (`sku`),
  CONSTRAINT `erp_ibfk_1` FOREIGN KEY (`sku`) REFERENCES `sku_details` (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
