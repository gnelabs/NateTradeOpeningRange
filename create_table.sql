CREATE TABLE `results` (
    `trade_id` VARCHAR(36) NOT NULL DEFAULT '0' COLLATE 'utf8mb4_general_ci',
    `stops_triggered` INT(11) NOT NULL DEFAULT '0',
    `trades_triggered` INT(11) NOT NULL DEFAULT '0',
    `net_profit` FLOAT NOT NULL DEFAULT '0',
    `average_holding_period` FLOAT NOT NULL DEFAULT '0',
    `trade_stats` JSON,
    PRIMARY KEY (trade_id),
    INDEX `ProfitIndex` (`net_profit`) USING BTREE
)
COMMENT='Stores backtest results for trades.'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;