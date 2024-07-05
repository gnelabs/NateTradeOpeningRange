CREATE TABLE `results` (
    `backtest_id` VARCHAR(5) NOT NULL DEFAULT '0' COLLATE 'utf8mb4_general_ci',
    `backtest_profit` FLOAT NOT NULL DEFAULT '0',
    `average_holding_period` FLOAT NOT NULL DEFAULT '0',
    `win_rate_percent` INT(3) NOT NULL DEFAULT '0',
    `stop_distance` FLOAT NOT NULL DEFAULT '0',
    `stop_count_limit` INT(11) NOT NULL DEFAULT '0',
    `stop_cooloff_period` INT(11) NOT NULL DEFAULT '0',
    `limit_distance` FLOAT NOT NULL DEFAULT '0',
    `trade_stats` JSON,
    PRIMARY KEY (backtest_id),
    INDEX `ProfitIndex` (`backtest_profit`) USING BTREE
)
COMMENT='Stores backtest results for trades.'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;