FACTORY_ABI = [
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "tokenA",
                "type": "address",
            },
            {
                "internalType": "address",
                "name": "tokenB",
                "type": "address",
            },
            {
                "internalType": "uint24",
                "name": "fee",
                "type": "uint24",
            },
        ],
        "name": "getPool",
        "outputs": [
            {
                "internalType": "address",
                "name": "pool",
                "type": "address",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


ERC20_ABI = [
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [
            {
                "internalType": "string",
                "name": "",
                "type": "string",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [
            {
                "internalType": "uint8",
                "name": "",
                "type": "uint8",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


POOL_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "fee",
        "outputs": [
            {
                "internalType": "uint24",
                "name": "",
                "type": "uint24",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "sender",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "recipient",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "amount0",
                "type": "int256",
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "amount1",
                "type": "int256",
            },
            {
                "indexed": False,
                "internalType": "uint160",
                "name": "sqrtPriceX96",
                "type": "uint160",
            },
            {
                "indexed": False,
                "internalType": "uint128",
                "name": "liquidity",
                "type": "uint128",
            },
            {
                "indexed": False,
                "internalType": "int24",
                "name": "tick",
                "type": "int24",
            },
        ],
        "name": "Swap",
        "type": "event",
    },
]